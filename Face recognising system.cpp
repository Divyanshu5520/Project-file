#include <opencv2/opencv.hpp>
#include <dlib/dnn.h>
#include <dlib/image_processing.h>
#include <dlib/opencv.h>
#include <iostream>
#include <fstream>
#include <ctime>
#include <vector>
#include <string>
#include <cstdio>  // For remove()

using namespace dlib;
using namespace std;

// --- Dlib network setup ---
template <template <int, template<typename> class, int, typename> class block,
          int N, template<typename> class bn_con, typename SUBNET>
using residual = add_prev1<block<N, bn_con, 1, tag1<SUBNET>>>;

template <int N, template<typename> class bn_con, int stride, typename SUBNET>
using block = bn_con<con<N, 3, 3, stride, stride, relu<bn_con<con<N, 3, 3, 1, 1, SUBNET>>>>>;

template <int N, typename SUBNET> using ares = relu<residual<block, N, affine, SUBNET>>;
template <typename SUBNET> using alevel0 = ares<256, SUBNET>;
template <typename SUBNET> using alevel1 = ares<128, SUBNET>;
template <typename SUBNET> using alevel2 = ares<64, SUBNET>;
template <typename SUBNET> using alevel3 = ares<32, SUBNET>;

using anet_type = loss_metric<fc_no_bias<128, avg_pool_everything<
                    alevel0<alevel1<alevel2<alevel3<
                    max_pool<3,3,2,2,relu<affine<con<32,7,7,2,2,
                    input_rgb_image_sized<150>>>>>>>>>>>>;

frontal_face_detector detector = get_frontal_face_detector();
shape_predictor sp;
anet_type net;

struct UserRecord {
    string name;
    vector<float> embedding;
    time_t lockout_time;
};

void save_user(const UserRecord& user) {
    ofstream file("users.db", ios::binary | ios::app);
    size_t name_len = user.name.size();
    file.write(reinterpret_cast<const char*>(&name_len), sizeof(size_t));
    file.write(user.name.c_str(), name_len);
    file.write(reinterpret_cast<const char*>(user.embedding.data()), user.embedding.size() * sizeof(float));
    file.write(reinterpret_cast<const char*>(&user.lockout_time), sizeof(time_t));
    file.close();
}

bool load_user(const string& name, UserRecord& user_out) {
    ifstream file("users.db", ios::binary);
    if (!file) return false;

    while (!file.eof()) {
        size_t name_len;
        file.read(reinterpret_cast<char*>(&name_len), sizeof(size_t));
        if (file.eof()) break;

        string uname(name_len, '\0');
        file.read(&uname[0], name_len);

        vector<float> embedding(128);
        file.read(reinterpret_cast<char*>(embedding.data()), 128 * sizeof(float));

        time_t lockout_time;
        file.read(reinterpret_cast<char*>(&lockout_time), sizeof(time_t));

        if (uname == name) {
            user_out = {uname, embedding, lockout_time};
            return true;
        }
    }

    return false;
}

void update_user_lockout(const string& name, time_t new_lockout) {
    ifstream infile("users.db", ios::binary);
    ofstream tempfile("temp.db", ios::binary);

    while (!infile.eof()) {
        size_t name_len;
        infile.read(reinterpret_cast<char*>(&name_len), sizeof(size_t));
        if (infile.eof()) break;

        string uname(name_len, '\0');
        infile.read(&uname[0], name_len);

        vector<float> embedding(128);
        infile.read(reinterpret_cast<char*>(embedding.data()), 128 * sizeof(float));

        time_t lockout_time;
        infile.read(reinterpret_cast<char*>(&lockout_time), sizeof(time_t));

        if (uname == name) lockout_time = new_lockout;

        tempfile.write(reinterpret_cast<const char*>(&name_len), sizeof(size_t));
        tempfile.write(uname.c_str(), name_len);
        tempfile.write(reinterpret_cast<const char*>(embedding.data()), 128 * sizeof(float));
        tempfile.write(reinterpret_cast<const char*>(&lockout_time), sizeof(time_t));
    }

    infile.close();
    tempfile.close();

    remove("users.db");
    rename("temp.db", "users.db");
}

void load_models() {
    deserialize("shape_predictor_68_face_landmarks.dat") >> sp;
    deserialize("dlib_face_recognition_resnet_model_v1.dat") >> net;
}

matrix<float, 0, 1> get_face_descriptor(cv::Mat& img) {
    cv_image<bgr_pixel> cimg(img);
    vector<rectangle> faces = detector(cimg);
    if (faces.empty()) return {};

    full_object_detection shape = sp(cimg, faces[0]);
    matrix<rgb_pixel> face_chip;
    extract_image_chip(cimg, get_face_chip_details(shape, 150, 0.25), face_chip);
    return net(face_chip);
}

double compare_embeddings(const matrix<float, 0, 1>& a, const vector<float>& b) {
    matrix<float, 0, 1> b_mat;
    b_mat.set_size(128);
    for (int i = 0; i < 128; ++i) b_mat(i) = b[i];
    return length(a - b_mat);
}

void register_user(const string& name, cv::VideoCapture& cap) {
    cout << "[INFO] Please look at the camera. Capturing face...\n";

    matrix<float, 0, 1> descriptor;
    int attempts = 0;

    while (attempts < 10) {
        cv::Mat frame;
        cap >> frame;
        descriptor = get_face_descriptor(frame);
        if (descriptor.size() != 0) break;

        cout << "[INFO] Face not detected. Try again...\n";
        attempts++;
    }

    if (descriptor.size() == 0) {
        cout << "[ERROR] Failed to detect a face after several attempts. Registration failed.\n";
        return;
    }

    vector<float> embedding(descriptor.begin(), descriptor.end());
    UserRecord new_user = {name, embedding, 0};
    save_user(new_user);
    cout << "[SUCCESS] User \"" << name << "\" registered successfully!\n";
}

int main() {
    load_models();

    cv::VideoCapture cap(0);
    if (!cap.isOpened()) {
        cerr << "[ERROR] Camera not accessible.\n";
        return 1;
    }

    string username;
    cout << "Enter your name: ";
    cin >> username;

    UserRecord user;
    time_t now = time(0);

    bool user_exists = load_user(username, user);
    if (user_exists && now < user.lockout_time) {
        cout << "[LOCKED] You are locked out until " << ctime(&user.lockout_time);
        return 1;
    }

    string file_to_protect;
    cout << "Enter the full path of the file to protect: ";
    cin >> file_to_protect;

    // Check if file exists before continuing
    ifstream test_file(file_to_protect);
    if (!test_file.good()) {
        cout << "[ERROR] File does not exist: " << file_to_protect << endl;
        return 1;
    }
    test_file.close();

    if (!user_exists) {
        cout << "[INFO] User not found. Do you want to register as \"" << username << "\"? (y/n): ";
        char choice;
        cin >> choice;
        if (choice == 'y' || choice == 'Y') {
            register_user(username, cap);
            return 0;
        } else {
            cout << "[CANCELLED] Registration cancelled.\n";
            return 1;
        }
    }

    int max_attempts = 3;
    bool access_granted = false;
    for (int i = 1; i <= max_attempts; ++i) {
        cout << "Attempt " << i << "/" << max_attempts << ": Look at the camera...\n";
        cv::Mat frame;
        cap >> frame;

        matrix<float, 0, 1> input_desc = get_face_descriptor(frame);
        if (input_desc.size() == 0) {
            cout << "[INFO] No face detected. Try again.\n";
            continue;
        }

        double dist = compare_embeddings(input_desc, user.embedding);
        if (dist < 0.6) {
            cout << "[ACCESS GRANTED] Welcome, " << username << "!\n";
            access_granted = true;
            break;
        } else {
            cout << "[ERROR] Face mismatch.\n";
        }
    }

    if (!access_granted) {
        cout << "[LOCKING] Too many failed attempts. Locking user for 24 hours.\n";
        update_user_lockout(username, now + 86400);

        // Delete protected file as requested
        if (remove(file_to_protect.c_str()) == 0) {
            cout << "[SECURITY] Protected file deleted due to failed authentication.\n";
        } else {
            cout << "[WARNING] Failed to delete protected file. Check permissions.\n";
        }

        return 1;
    }

    // Access granted, do nothing to the file
    cout << "[INFO] File access allowed: " << file_to_protect << endl;
    return 0;
}

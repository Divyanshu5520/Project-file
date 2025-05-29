#include <QApplication>
#include <QMainWindow>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QTimer>
#include <QMessageBox>

#include <opencv2/opencv.hpp>
#include <dlib/opencv.h>
#include <dlib/dnn.h>
#include <dlib/image_processing.h>

#include <windows.h>
#include <sapi.h>

#include <fstream>
#include <vector>
#include <ctime>
#include <cstdio>

// Dlib network blocks for face recognition model
template <template <int, template<typename> class, int, typename> class block,
          int N, template<typename> class bn_con, typename SUBNET>
using residual = dlib::add_prev1<block<N, bn_con, 1, dlib::tag1<SUBNET>>>;

template <int N, template<typename> class bn_con, int stride, typename SUBNET>
using block  = bn_con<dlib::con<N,3,3,stride,stride,dlib::relu<bn_con<dlib::con<N,3,3,1,1,SUBNET>>>>>;

template <int N, typename SUBNET> using ares = dlib::relu<residual<block,N,dlib::affine,SUBNET>>;

using anet_type = dlib::loss_metric<dlib::fc_no_bias<128,dlib::avg_pool_everything<
                        ares<256,
                        ares<128,
                        ares<64,
                        ares<32,
                        dlib::max_pool<3,3,2,2,dlib::relu<dlib::affine<dlib::con<32,7,7,2,2,
                        dlib::input_rgb_image_sized<150>>>>>>>>>>>>>;
                        
struct UserRecord {
    std::string name;
    std::vector<float> embedding; // 128 floats
    time_t lockout_time;
};

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    MainWindow(QWidget *parent=nullptr) : QMainWindow(parent), attemptCount(0), pVoice(nullptr) {
        // Setup UI
        cameraLabel = new QLabel("Camera feed");
        cameraLabel->setFixedSize(640, 480);
        usernameLineEdit = new QLineEdit();
        usernameLineEdit->setPlaceholderText("Username");
        fileLineEdit = new QLineEdit();
        fileLineEdit->setPlaceholderText("File to protect");

        startCameraButton = new QPushButton("Start Camera");
        registerButton = new QPushButton("Register User");
        authenticateButton = new QPushButton("Authenticate & Protect File");

        QHBoxLayout *hLayout = new QHBoxLayout();
        hLayout->addWidget(startCameraButton);
        hLayout->addWidget(registerButton);
        hLayout->addWidget(authenticateButton);

        QVBoxLayout *vLayout = new QVBoxLayout();
        vLayout->addWidget(cameraLabel);
        vLayout->addWidget(usernameLineEdit);
        vLayout->addWidget(fileLineEdit);
        vLayout->addLayout(hLayout);

        QWidget *widget = new QWidget();
        widget->setLayout(vLayout);
        setCentralWidget(widget);

        // Connect buttons
        connect(startCameraButton, &QPushButton::clicked, this, &MainWindow::onStartCameraClicked);
        connect(registerButton, &QPushButton::clicked, this, &MainWindow::onRegisterClicked);
        connect(authenticateButton, &QPushButton::clicked, this, &MainWindow::onAuthenticateClicked);

        timer = new QTimer(this);
        connect(timer, &QTimer::timeout, this, &MainWindow::captureFrame);

        // Load Dlib models
        detector = dlib::get_frontal_face_detector();
        try {
            dlib::deserialize("shape_predictor_68_face_landmarks.dat") >> sp;
            dlib::deserialize("dlib_face_recognition_resnet_model_v1.dat") >> net;
        } catch (...) {
            QMessageBox::critical(this, "Error", "Failed to load dlib models. Make sure data files are in working dir.");
            exit(1);
        }

        // Init COM for voice
        if (FAILED(::CoInitialize(nullptr))) {
            QMessageBox::warning(this, "Voice Init", "Failed to initialize COM.");
        }
        HRESULT hr = CoCreateInstance(CLSID_SpVoice, NULL, CLSCTX_ALL, IID_ISpVoice, (void **)&pVoice);
        if (FAILED(hr)) pVoice = nullptr;

        setWindowTitle("Face Recognition File Protector");
        resize(700, 650);
    }

    ~MainWindow() {
        if(pVoice) pVoice->Release();
        ::CoUninitialize();
        if(cap.isOpened()) cap.release();
    }

private slots:
    void onStartCameraClicked() {
        if (!cap.isOpened()) {
            cap.open(0);
            if (!cap.isOpened()) {
                QMessageBox::critical(this, "Camera", "Failed to open camera");
                return;
            }
            timer->start(30);
            speak("Camera started.");
        }
    }

    void captureFrame() {
        cv::Mat frame;
        cap >> frame;
        if (frame.empty()) return;
        cv::cvtColor(frame, frame, cv::COLOR_BGR2RGB);
        QImage qimg((uchar*)frame.data, frame.cols, frame.rows, frame.step, QImage::Format_RGB888);
        cameraLabel->setPixmap(QPixmap::fromImage(qimg).scaled(cameraLabel->size(), Qt::KeepAspectRatio));
        lastFrame = frame.clone();
    }

    void onRegisterClicked() {
        QString qname = usernameLineEdit->text();
        if (qname.isEmpty()) {
            QMessageBox::warning(this, "Input", "Enter username");
            return;
        }
        if (!cap.isOpened()) {
            QMessageBox::warning(this, "Camera", "Start the camera first");
            return;
        }
        speak("Look at the camera for registration.");

        matrix<float,0,1> descriptor;
        int tries = 0;
        while (tries < 10) {
            if (lastFrame.empty()) {
                QThread::msleep(200);
                tries++;
                continue;
            }
            descriptor = get_face_descriptor(lastFrame);
            if (descriptor.size() != 0) break;
            QThread::msleep(200);
            tries++;
        }

        if (descriptor.size() == 0) {
            speak("Face not detected. Registration failed.");
            QMessageBox::warning(this, "Register", "Failed to detect face.");
            return;
        }

        std::vector<float> emb(descriptor.begin(), descriptor.end());
        UserRecord u = {qname.toStdString(), emb, 0};
        save_user(u);

        speak("Registration successful.");
        QMessageBox::information(this, "Register", "User registered.");
    }

    void onAuthenticateClicked() {
        QString qname = usernameLineEdit->text();
        QString qfile = fileLineEdit->text();
        if (qname.isEmpty() || qfile.isEmpty()) {
            QMessageBox::warning(this, "Input", "Enter username and file path");
            return;
        }
        if (!cap.isOpened()) {
            QMessageBox::warning(this, "Camera", "Start the camera first");
            return;
        }
        if (!QFile::exists(qfile)) {
            QMessageBox::warning(this, "File", "File does not exist");
            return;
        }

        UserRecord user;
        if (!load_user(qname.toStdString(), user)) {
            QMessageBox::warning(this, "User", "User not found. Register first.");
            return;
        }

        time_t now = time(nullptr);
        if (now < user.lockout_time) {
            QMessageBox::warning(this, "Locked", "User locked out until " + QString::fromStdString(ctime(&user.lockout_time)));
            return;
        }

        attemptCount = 0;
        bool accessGranted = false;

        while (attemptCount < 3) {
            attemptCount++;
            speak(QString("Attempt %1. Look at the camera.").arg(attemptCount));

            QThread::msleep(2000); // wait 2 seconds to allow user to position

            if (lastFrame.empty()) continue;

            matrix<float,0,1> input_desc = get_face_descriptor(lastFrame);
            if (input_desc.size() == 0) {
                speak("No face detected. Try again.");
                continue;
            }

            double dist = compare_embeddings(input_desc, user.embedding);
            if (dist < 0.6) {
                speak("Access granted. Welcome " + qname);
                QMessageBox::information(this, "Access", "Access granted!");
                accessGranted = true;
                break;
            } else {
                speak("Face does not match. Try again.");
            }
        }

        if (!accessGranted) {
            speak("Too many failed attempts. Locking user and deleting file.");
            QMessageBox::critical(this, "Access Denied", "Too many failed attempts. User locked for 24 hours and file deleted.");

            update_user_lockout(qname.toStdString(), now + 86400);

            if (std::remove(qfile.toStdString().c_str()) == 0) {
                speak("Protected file deleted.");
            } else {
                speak("Failed to delete protected file.");
            }
        }
    }

private:
    QLabel *cameraLabel;
    QLineEdit *usernameLineEdit;
    QLineEdit *fileLineEdit;
    QPushButton *startCameraButton;
    QPushButton *registerButton;
    QPushButton *authenticateButton;

    QTimer *timer;
    cv::VideoCapture cap;
    cv::Mat lastFrame;

    dlib::frontal_face_detector detector;
    dlib::shape_predictor sp;
    anet_type net;

    ISpVoice *pVoice;
    int attemptCount;

    matrix<float,0,1> get_face_descriptor(cv::Mat &img) {
        dlib::cv_image<dlib::bgr_pixel> cimg(img);
        std::vector<dlib::rectangle> faces = detector(cimg);
        if (faces.empty()) return {};

        dlib::full_object_detection shape = sp(cimg, faces[0]);
        dlib::matrix<dlib::rgb_pixel> face_chip;
        extract_image_chip(cimg, get_face_chip_details(shape,150,0.25), face_chip);
        return net(face_chip);
    }

    double compare_embeddings(const matrix<float,0,1> &a, const std::vector<float> &b) {
        dlib::matrix<float,0,1> b_mat;
        b_mat.set_size(128);
        for (int i=0; i<128; ++i) b_mat(i) = b[i];
        return length(a - b_mat);
    }

    bool load_user(const std::string &name, UserRecord &user_out) {
        std::ifstream file("users.db", std::ios::binary);
        if (!file) return false;
        while (!file.eof()) {
            size_t name_len;
            file.read(reinterpret_cast<char*>(&name_len), sizeof(size_t));
            if (file.eof()) break;

            std::string uname(name_len, '\0');
            file.read(&uname[0], name_len);

            std::vector<float> embedding(128);
            file.read(reinterpret_cast<char*>(embedding.data()), 128*sizeof(float));

            time_t lockout_time;
            file.read(reinterpret_cast<char*>(&lockout_time), sizeof(time_t));

            if (uname == name) {
                user_out = {uname, embedding, lockout_time};
                return true;
            }
        }
        return false;
    }

    void save_user(const UserRecord &user) {
        std::ofstream file("users.db", std::ios::binary | std::ios::app);
        size_t name_len = user.name.size();
        file.write(reinterpret_cast<const char*>(&name_len), sizeof(size_t));
        file.write(user.name.c_str(), name_len);
        file.write(reinterpret_cast<const char*>(user.embedding.data()), user.embedding.size()*sizeof(float));
        file.write(reinterpret_cast<const char*>(&user.lockout_time), sizeof(time_t));
        file.close();
    }

    void update_user_lockout(const std::string &name, time_t new_lockout) {
        std::ifstream infile("users.db", std::ios::binary);
        std::ofstream tempfile("temp.db", std::ios::binary);

        while (!infile.eof()) {
            size_t name_len;
            infile.read(reinterpret_cast<char*>(&name_len), sizeof(size_t));
            if (infile.eof()) break;

            std::string uname(name_len, '\0');
            infile.read(&uname[0], name_len);

            std::vector<float> embedding(128);
            infile.read(reinterpret_cast<char*>(embedding.data()), 128*sizeof(float));

            time_t lockout_time;
            infile.read(reinterpret_cast<char*>(&lockout_time), sizeof(time_t));

            if (uname == name) lockout_time = new_lockout;

            tempfile.write(reinterpret_cast<const char*>(&name_len), sizeof(size_t));
            tempfile.write(uname.c_str(), name_len);
            tempfile.write(reinterpret_cast<const char*>(embedding.data()), 128*sizeof(float));
            tempfile.write(reinterpret_cast<const char*>(&lockout_time), sizeof(time_t));
        }
        infile.close();
        tempfile.close();

        std::remove("users.db");
        std::rename("temp.db", "users.db");
    }

    void speak(const QString &text) {
        if (!pVoice) return;
        std::wstring wtext = text.toStdWString();
        pVoice->Speak(wtext.c_str(), SPF_ASYNC, NULL);
    }
};

#include "main.moc"

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    MainWindow w;
    w.show();
    return a.exec();
}

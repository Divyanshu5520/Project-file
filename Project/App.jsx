// App.jsx

import React, { useEffect, useState, useRef } from "react";
import { db } from "./firebase";
import {
  collection,
  addDoc,
  query,
  orderBy,
  onSnapshot,
  serverTimestamp,
  doc,
  setDoc,
  getDocs,
  deleteDoc
} from "firebase/firestore";

export default function App() {
  const [username, setUsername] = useState("");
  const [avatar, setAvatar] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [room, setRoom] = useState("general");
  const [rooms, setRooms] = useState(["general"]);
  const [typingUsers, setTypingUsers] = useState([]);
  const inputRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    const storedName = localStorage.getItem("username");
    const storedAvatar = localStorage.getItem("avatar");
    const name = storedName || prompt("Enter your username:") || "Anonymous";
    const avatarUrl = storedAvatar || prompt("Enter avatar URL:") || "https://via.placeholder.com/40";
    setUsername(name);
    setAvatar(avatarUrl);
    localStorage.setItem("username", name);
    localStorage.setItem("avatar", avatarUrl);
  }, []);

  useEffect(() => {
    const savedRoom = localStorage.getItem("lastRoom");
    if (savedRoom) setRoom(savedRoom);
  }, []);

  useEffect(() => {
    localStorage.setItem("lastRoom", room);
    inputRef.current?.focus();
  }, [room]);

  useEffect(() => {
    const q = query(
      collection(db, "rooms", room, "messages"),
      orderBy("timestamp")
    );
    const unsub = onSnapshot(q, (snapshot) => {
      setMessages(snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() })));
    });
    return () => unsub();
  }, [room]);

  useEffect(() => {
    const fetchRooms = async () => {
      const snap = await getDocs(collection(db, "rooms"));
      setRooms(snap.docs.map((doc) => doc.id).sort());
    };
    fetchRooms();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const unsub = onSnapshot(collection(db, "rooms", room, "typing"), (snapshot) => {
      setTypingUsers(
        snapshot.docs
          .map((doc) => doc.id)
          .filter((name) => name !== username)
      );
    });
    return () => unsub();
  }, [room, username]);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    await addDoc(collection(db, "rooms", room, "messages"), {
      text: message,
      user: username,
      avatar,
      timestamp: serverTimestamp(),
    });
    await deleteDoc(doc(db, "rooms", room, "typing", username));
    setMessage("");
    inputRef.current?.focus();
  };

  const handleTyping = async (val) => {
    setMessage(val);
    if (val.trim()) {
      await setDoc(doc(db, "rooms", room, "typing", username), { typing: true });
    } else {
      await deleteDoc(doc(db, "rooms", room, "typing", username));
    }
  };

  const createRoom = async () => {
    const newRoom = prompt("Enter new room name:");
    if (!newRoom) return;
    await setDoc(doc(db, "rooms", newRoom), {});
    setRoom(newRoom);
    setRooms((prev) => [...new Set([...prev, newRoom])]);
  };

  const deleteMessage = async (id) => {
    await deleteDoc(doc(db, "rooms", room, "messages", id));
  };

  const formatTime = (timestamp) => {
    try {
      return timestamp?.toDate().toLocaleTimeString() || "Sending...";
    } catch {
      return "Sending...";
    }
  };

  return (
    <div className="flex h-screen bg-gray-900 text-white">
      {/* Sidebar */}
      <div className="w-1/4 p-4 border-r border-gray-700">
        <h2 className="text-xl font-bold mb-4">Rooms</h2>
        <ul>
          {rooms.map((r) => (
            <li
              key={r}
              className={`cursor-pointer p-2 rounded ${room === r ? "bg-cyan-700" : "hover:bg-gray-700"}`}
              onClick={() => setRoom(r)}
            >
              #{r}
            </li>
          ))}
        </ul>
        <button onClick={createRoom} className="mt-4 px-3 py-1 bg-cyan-600 rounded">
          + New Room
        </button>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-2xl">Room: #{room}</h1>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2 flex flex-col">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500">No messages yet</div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-2 p-2 rounded ${msg.user === username ? "bg-cyan-800 self-end" : "bg-gray-800"}`}
              >
                <img src={msg.avatar} alt="avatar" className="w-8 h-8 rounded-full" />
                <div>
                  <div className="text-sm font-semibold">{msg.user}</div>
                  <div className="text-xs text-gray-400">@ {formatTime(msg.timestamp)}</div>
                  <div>{msg.text}</div>
                  {msg.user === username && (
                    <button
                      onClick={() => deleteMessage(msg.id)}
                      className="text-xs text-red-400 hover:underline"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={chatEndRef} />
        </div>
        <form onSubmit={sendMessage} className="flex flex-col p-4 border-t border-gray-700">
          {typingUsers.length > 0 && (
            <div className="text-sm text-gray-400 mb-2">
              {typingUsers.join(", ")} typing...
            </div>
          )}
          <textarea
            ref={inputRef}
            value={message}
            onChange={(e) => handleTyping(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(e);
              }
            }}
            className="flex-1 p-2 rounded bg-gray-800 border border-gray-600 resize-none"
            placeholder="Type a message..."
          />
          <button type="submit" className="mt-2 px-4 py-2 bg-cyan-600 rounded">
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

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
} from "firebase/firestore";

export default function App() {
  const [username, setUsername] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [room, setRoom] = useState("general");
  const [rooms, setRooms] = useState(["general"]);
  const inputRef = useRef(null);

  useEffect(() => {
    const name = prompt("Enter your username:") || "Anonymous";
    setUsername(name);
  }, []);

  useEffect(() => {
    const q = query(
      collection(db, "rooms", room, "messages"),
      orderBy("timestamp")
    );
    const unsub = onSnapshot(q, (snapshot) => {
      setMessages(snapshot.docs.map((doc) => doc.data()));
    });
    return () => unsub();
  }, [room]);

  useEffect(() => {
    const fetchRooms = async () => {
      const snap = await getDocs(collection(db, "rooms"));
      setRooms(snap.docs.map((doc) => doc.id));
    };
    fetchRooms();
  }, []);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    await addDoc(collection(db, "rooms", room, "messages"), {
      text: message,
      user: username,
      timestamp: serverTimestamp(),
    });
    setMessage("");
    inputRef.current?.focus();
  };

  const createRoom = async () => {
    const newRoom = prompt("Enter new room name:");
    if (!newRoom) return;
    await setDoc(doc(db, "rooms", newRoom), {});
    setRoom(newRoom);
    setRooms((prev) => [...new Set([...prev, newRoom])]); // Avoid duplicates
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
              className={`cursor-pointer p-2 rounded ${
                room === r ? "bg-cyan-700" : "hover:bg-gray-700"
              }`}
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
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {messages.map((msg, i) => (
            <div key={i} className="bg-gray-800 p-2 rounded">
              <strong>{msg.user}</strong>{" "}
              <span className="text-sm text-gray-400">
                @ {formatTime(msg.timestamp)}
              </span>
              <div>{msg.text}</div>
            </div>
          ))}
        </div>
        <form onSubmit={sendMessage} className="flex p-4 border-t border-gray-700">
          <input
            ref={inputRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="flex-1 p-2 rounded bg-gray-800 border border-gray-600"
            placeholder="Type a message..."
          />
          <button type="submit" className="ml-2 px-4 py-2 bg-cyan-600 rounded">
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

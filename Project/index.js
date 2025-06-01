// index.js

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css'; // Tailwind CSS or custom styles
import App from './App';
// import { BrowserRouter } from 'react-router-dom'; // Uncomment if using routing

const root = ReactDOM.createRoot(document.getElementById('root'));

root.render(
  <React.StrictMode>
    {/* Uncomment <BrowserRouter> if you're using React Router */}
    {/* <BrowserRouter> */}
      <App />
    {/* </BrowserRouter> */}
  </React.StrictMode>
);

# 🧠 My AI Chatbot

A simple FastAPI-powered chatbot using Google's Gemini Pro model.  
Frontend is built with HTML and JavaScript, and deployed on Netlify.  
Backend is deployed on Render.

---

## 🚀 Live Demo

- **Frontend**: [https://my-ai-chat.netlify.app](https://my-ai-chat.netlify.app)  
- **Backend**: [https://my-ai-chat.onrender.com](https://my-ai-chat.onrender.com)

---

## 🛠️ Tech Stack

- **Frontend**: HTML, JavaScript
- **Backend**: FastAPI, Uvicorn
- **AI Model**: Gemini Pro via `google-generativeai`
- **Hosting**: Netlify (frontend), Render (backend)

---

## 📦 Installation (Local)

```bash
pip install -r requirements.txt
uvicorn server:app --reload

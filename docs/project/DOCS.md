# 📚 AgriAI Documentation

## 📖 Tài Liệu Dự Án

### 🚀 Bắt Đầu Nhanh
- **[START_BACKEND.md](START_BACKEND.md)** - Hướng dẫn bắt đầu nhanh với SQL Server
- **[README.md](../../README.md)** - Tổng quan dự án và cài đặt

### 🗄️ Database
- **[NongNghiepAI_Full.sql](../database/NongNghiepAI_Full.sql)** - ⭐ Complete SQL Server schema (10 tables + seed data)

### 🔌 API
- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - Chi tiết các API endpoints
- **API Docs (Live):** http://localhost:8000/docs

### 🛠️ Development
- **[CONTRIBUTING.md](../../CONTRIBUTING.md)** - Hướng dẫn đóng góp code
- **[CHANGELOG.md](../../CHANGELOG.md)** - Lịch sử thay đổi
- **[TOD0.md](TOD0.md)** - Danh sách công việc cần làm

### 🚢 Deployment
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Hướng dẫn triển khai production

---

## 🎯 Quick Links

### Setup Database
```bash
# Chạy SQL script trong SSMS
# File: ../database/NongNghiepAI_Full.sql (10 tables)
```

### Start Backend
```bash
cd backend
uvicorn app.main:app --reload
```

### Start Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend calls Backend through `VITE_API_URL` in `frontend/.env.example`.
Default value:
```env
VITE_API_URL=http://localhost:8000
```

### Access Application
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## 📞 Contact

**Project Maintainer:** Trần Thị Mỹ  
**Email:** [tranthimy2205@gmail.com](mailto:tranthimy2205@gmail.com)

---

## 📁 Project Structure

```
agri-ai/
├── backend/              # FastAPI backend
│   ├── app/             # Application code
│   ├── ai_models/       # AI models (YOLO, Prophet)
│   └── crawler/         # Data crawlers
│
├── frontend/            # React frontend
│   ├── src/            # Source code
│   └── public/         # Static files
│
├── scripts/            # Utility scripts
├── docs/database/      # Database schema and SQL
└── training/           # Model training workflows and checkpoints
```

---

## 🔑 Key Features

1. **Quality Check** - AI-powered crop quality assessment
2. **Price Forecasting** - Predict market prices
3. **Harvest Planning** - Optimize harvest schedules
4. **Market Analysis** - Compare prices across regions
5. **Alert System** - Price change notifications

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, Python 3.11+
- **Frontend:** React 18, Vite, Tailwind CSS
- **Database:** SQL Server
- **AI/ML:** YOLOv8, Scikit-learn, Prophet
- **Cache:** Redis

---

**Built with ❤️ for Vietnamese farmers**

# Training workspace

## Quality

- `quality/prepare_dataset.py` chia dữ liệu ảnh thành train/validation.
- `quality/train_quality_cnn.py` huấn luyện EfficientNet.
- `quality/streamlit_quality.py` là giao diện kiểm tra qua backend.
- `quality/checkpoints/` chứa checkpoint được theo dõi trong Git.
- `quality/notebooks/` chứa notebook chạy trên Colab/Kaggle.

## YOLO

`yolo/` chứa recipe, notebook và hướng dẫn huấn luyện YOLO11.
Checkpoint production sau khi kiểm tra vẫn được deploy vào
`backend/ai_models/weights/` bằng `python scripts/setup_models.py`.

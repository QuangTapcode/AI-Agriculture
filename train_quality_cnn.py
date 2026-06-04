"""
Train EfficientNet-B0 để chấm chất lượng nông sản
Classes: Fresh / Semi-fresh / Semi-rotten / Rotten  (hoặc Loại1 / Loại2 / Hỏng)

Cấu trúc thư mục dataset:
  data/
    train/
      fresh/        *.jpg
      semifresh/    *.jpg
      semirotten/   *.jpg
      rotten/       *.jpg
    val/
      fresh/
      ...

Chạy:
  pip install torch torchvision tqdm matplotlib scikit-learn
  python train_quality_cnn.py
"""

import os
import copy
import time
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay

# ──────────────────────────────────────────────
# 1. CẤU HÌNH
# ──────────────────────────────────────────────
DATA_DIR   = "data"          # thư mục chứa train/ và val/
NUM_CLASSES = 4              # thay thành 3 nếu chỉ có Loại1/Loại2/Hỏng
BATCH_SIZE  = 32
NUM_EPOCHS  = 30
LR          = 1e-3
DEVICE      = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SAVE_PATH   = "efficientnet_quality.pt"

print(f"[INFO] Device: {DEVICE}")

# ──────────────────────────────────────────────
# 2. DATA AUGMENTATION & LOADING
# ──────────────────────────────────────────────
train_tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(30),
    transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1),
    transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],   # ImageNet mean/std
                         [0.229, 0.224, 0.225]),
])

val_tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

train_ds = datasets.ImageFolder(os.path.join(DATA_DIR, "train"), transform=train_tf)
val_ds   = datasets.ImageFolder(os.path.join(DATA_DIR, "val"),   transform=val_tf)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=4, pin_memory=True)
val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)

CLASS_NAMES = train_ds.classes
print(f"[INFO] Classes: {CLASS_NAMES}")
print(f"[INFO] Train: {len(train_ds)} | Val: {len(val_ds)}")

# ──────────────────────────────────────────────
# 3. MODEL — EfficientNet-B0 Transfer Learning
# ──────────────────────────────────────────────
model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)

# Đóng băng backbone, chỉ train lớp cuối
for param in model.parameters():
    param.requires_grad = False

# Thay classifier
model.classifier[1] = nn.Linear(1280, NUM_CLASSES)

model = model.to(DEVICE)

# ──────────────────────────────────────────────
# 4. LOSS, OPTIMIZER, SCHEDULER
# ──────────────────────────────────────────────
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.classifier.parameters(), lr=LR)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

# ──────────────────────────────────────────────
# 5. TRAINING LOOP
# ──────────────────────────────────────────────
def run_epoch(loader, is_train):
    if is_train:
        model.train()
    else:
        model.eval()

    total_loss, correct, total = 0.0, 0, 0
    with torch.set_grad_enabled(is_train):
        for imgs, labels in loader:
            imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
            outputs = model(imgs)
            loss = criterion(outputs, labels)

            if is_train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * imgs.size(0)
            preds = outputs.argmax(dim=1)
            correct += (preds == labels).sum().item()
            total   += imgs.size(0)

    return total_loss / total, correct / total


history = {"train_acc": [], "val_acc": [], "train_loss": [], "val_loss": []}
best_acc    = 0.0
best_weights = None

print("\n[INFO] Bắt đầu training...\n")
for epoch in range(1, NUM_EPOCHS + 1):
    t0 = time.time()
    tr_loss, tr_acc = run_epoch(train_loader, is_train=True)
    vl_loss, vl_acc = run_epoch(val_loader,   is_train=False)
    scheduler.step()

    history["train_acc"].append(tr_acc)
    history["val_acc"].append(vl_acc)
    history["train_loss"].append(tr_loss)
    history["val_loss"].append(vl_loss)

    if vl_acc > best_acc:
        best_acc     = vl_acc
        best_weights = copy.deepcopy(model.state_dict())

    print(f"Epoch {epoch:3d}/{NUM_EPOCHS}  "
          f"train_loss={tr_loss:.4f}  train_acc={tr_acc:.3f}  "
          f"val_loss={vl_loss:.4f}  val_acc={vl_acc:.3f}  "
          f"[{time.time()-t0:.1f}s]"
          + (" ← best" if vl_acc == best_acc else ""))

# ──────────────────────────────────────────────
# 6. LƯU WEIGHTS TỐT NHẤT
# ──────────────────────────────────────────────
model.load_state_dict(best_weights)
torch.save(model.state_dict(), SAVE_PATH)
print(f"\n[INFO] Saved best model → {SAVE_PATH}  (val_acc={best_acc:.3f})")

# ──────────────────────────────────────────────
# 7. BIỂU ĐỒ ACCURACY & LOSS
# ──────────────────────────────────────────────
epochs_range = range(1, NUM_EPOCHS + 1)
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].plot(epochs_range, history["train_acc"], label="Train")
axes[0].plot(epochs_range, history["val_acc"],   label="Val")
axes[0].set_title("Accuracy")
axes[0].set_xlabel("Epoch"); axes[0].legend()

axes[1].plot(epochs_range, history["train_loss"], label="Train")
axes[1].plot(epochs_range, history["val_loss"],   label="Val")
axes[1].set_title("Loss")
axes[1].set_xlabel("Epoch"); axes[1].legend()

plt.tight_layout()
plt.savefig("training_curves.png", dpi=150)
print("[INFO] Saved training_curves.png")

# ──────────────────────────────────────────────
# 8. CONFUSION MATRIX
# ──────────────────────────────────────────────
model.eval()
all_preds, all_labels = [], []
with torch.no_grad():
    for imgs, labels in val_loader:
        imgs = imgs.to(DEVICE)
        preds = model(imgs).argmax(dim=1).cpu().tolist()
        all_preds  += preds
        all_labels += labels.tolist()

cm = confusion_matrix(all_labels, all_preds)
disp = ConfusionMatrixDisplay(cm, display_labels=CLASS_NAMES)
fig2, ax2 = plt.subplots(figsize=(6, 5))
disp.plot(ax=ax2, cmap="Blues", colorbar=False)
ax2.set_title("Confusion Matrix (Val)")
plt.tight_layout()
plt.savefig("confusion_matrix.png", dpi=150)
print("[INFO] Saved confusion_matrix.png")

# ──────────────────────────────────────────────
# 9. INFERENCE HELPER — dùng trong pipeline YOLO
# ──────────────────────────────────────────────
def load_model(path=SAVE_PATH, num_classes=NUM_CLASSES):
    """Load model đã train để predict."""
    m = models.efficientnet_b0(weights=None)
    m.classifier[1] = nn.Linear(1280, num_classes)
    m.load_state_dict(torch.load(path, map_location="cpu"))
    m.eval()
    return m


def predict_crop(model, crop_bgr):
    """
    Nhận crop BGR (numpy array từ OpenCV), trả về (class_name, confidence).
    Dùng sau khi YOLO detect xong, crop box ra rồi gọi hàm này.
    """
    import cv2
    import numpy as np
    from PIL import Image

    # BGR → RGB → PIL
    img = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))
    tensor = val_tf(img).unsqueeze(0)          # [1, 3, 224, 224]
    with torch.no_grad():
        logits = model(tensor)
        probs  = torch.softmax(logits, dim=1)[0]
        idx    = probs.argmax().item()
    return CLASS_NAMES[idx], float(probs[idx])


# ── Quick test ──
if __name__ == "__main__":
    print("\n[TEST] Load model và chạy thử predict_crop...")
    m = load_model()
    import numpy as np
    dummy = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    cls, conf = predict_crop(m, dummy)
    print(f"  → class={cls}, confidence={conf:.3f}  (dummy input, kết quả ngẫu nhiên)")
    print("\nDone! Tích hợp vào pipeline YOLO:")
    print("  quality_model = load_model('efficientnet_quality.pt')")
    print("  cls, conf = predict_crop(quality_model, crop_bgr)")

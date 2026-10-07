# Annual Report Tech Analyzer

Ứng dụng Streamlit phân tích việc áp dụng ERP và công nghệ trong kế toán từ báo cáo thường niên. Ứng dụng tải PDF, trích xuất chữ, đếm từ khóa theo ngữ cảnh câu, chấm mức áp dụng, giữ số trang và xuất CSV.

## Chạy trên máy

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Publish miễn phí bằng Streamlit Community Cloud

1. Tạo repository public trên GitHub.
2. Upload `app.py` và `requirements.txt` vào repository.
3. Mở [share.streamlit.io](https://share.streamlit.io).
4. Chọn repository, branch, file `app.py`.
5. Bấm Deploy.
6. Gửi URL ứng dụng cho người khác.

## Cách đánh giá

- Bộ từ khóa chia thành ERP, công nghệ kế toán, ngữ cảnh kế toán, hành động, vận hành, kế hoạch và phủ định.
- ERP hoặc công nghệ chung chỉ là bằng chứng liên quan kế toán khi xuất hiện cùng ngữ cảnh kế toán trong cùng câu.
- `adoption_score`: `0` không có bằng chứng, `1` chỉ đề cập, `2` có kế hoạch, `3` đang triển khai/áp dụng, `4` đã áp dụng/đang vận hành.
- `tech_adoption=1` chỉ khi có bằng chứng mức `3` hoặc `4`. Câu có cụm phủ định như `chưa triển khai` không được tính là đã áp dụng.
- Luôn đọc cột `evidence` trước khi dùng dữ liệu nghiên cứu. Đây là bộ phân loại từ khóa, chưa phải phân tích ngữ nghĩa hoàn toàn.
- Báo cáo scan ảnh cần OCR; bản hiện tại xử lý PDF có lớp text.

## Tự kiểm tra

```powershell
python self_check.py
```

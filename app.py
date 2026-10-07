import csv
import io
import ipaddress
import re
import socket
import unicodedata
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import streamlit as st
from pypdf import PdfReader

DEFAULT_ERP_TERMS = """ERP
hệ thống ERP
phần mềm ERP
enterprise resource planning
SAP ERP
SAP S/4HANA
Oracle ERP
Oracle Fusion
Microsoft Dynamics
Odoo
NetSuite
Infor ERP
MISA
FAST Accounting
BRAVO"""

DEFAULT_ACCOUNTING_TECH_TERMS = """phần mềm kế toán
hệ thống kế toán
hệ thống thông tin kế toán
kế toán điện tử
accounting software
accounting information system
cloud accounting
hóa đơn điện tử
electronic invoice
e-invoice
chữ ký số
tự động hóa kế toán
accounting automation
RPA
robotic process automation
trí tuệ nhân tạo
artificial intelligence
machine learning
OCR
nhận dạng ký tự quang học
phân tích dữ liệu
data analytics
business intelligence
XBRL
blockchain"""

DEFAULT_ACCOUNTING_CONTEXT = """kế toán
phòng kế toán
bộ phận kế toán
tài chính kế toán
financial accounting
finance and accounting
báo cáo tài chính
financial reporting
sổ cái
general ledger
công nợ phải thu
công nợ phải trả
accounts receivable
accounts payable
đối soát
thuế
tax
hóa đơn
invoice
kiểm toán
audit"""

DEFAULT_ACTION_TERMS = """triển khai
đã triển khai
đang triển khai
áp dụng
đã áp dụng
sử dụng
đang sử dụng
vận hành
đưa vào sử dụng
tích hợp
kết nối
nâng cấp
thay thế
chuyển sang
đầu tư
tự động hóa
số hóa
implemented
deployed
adopted
used
in operation
go-live
integrated
upgraded
automated
digitized"""

DEFAULT_OPERATIONAL_TERMS = """đã triển khai
đã áp dụng
đang sử dụng
đưa vào sử dụng
đang vận hành
vận hành
go-live
in operation
implemented
deployed
adopted
used"""
DEFAULT_PLANNED_TERMS = """dự kiến
kế hoạch
sẽ triển khai
sẽ áp dụng
sẽ sử dụng
đang xem xét
planned
will implement
will deploy
to be implemented"""
DEFAULT_NEGATIVE_TERMS = """chưa triển khai
chưa áp dụng
chưa sử dụng
chưa đưa vào sử dụng
không triển khai
không áp dụng
không sử dụng
not implemented
not deployed
not in use
not adopted"""
ACCOUNTING_SPECIFIC_MARKERS = (
    "ke toan", "accounting", "hoa don", "invoice", "so cai", "general ledger",
    "accounts payable", "accounts receivable", "xbrl", "thue", "tax",
)


def public_url(raw_url: str) -> str:
    url = raw_url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL phải bắt đầu bằng http:// hoặc https://")
    host = parsed.hostname
    try:
        addresses = socket.getaddrinfo(host, None)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError("URL trỏ tới địa chỉ mạng nội bộ, bị từ chối")
    except socket.gaierror as exc:
        raise ValueError(f"Không phân giải được tên miền: {host}") from exc
    return url


def download_pdf(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "AnnualReportTechAnalyzer/1.0"})
    with urlopen(request, timeout=30) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        data = response.read(30 * 1024 * 1024 + 1)
    if len(data) > 30 * 1024 * 1024:
        raise ValueError("PDF vượt giới hạn 30 MB")
    if "pdf" not in content_type and not data.startswith(b"%PDF"):
        raise ValueError("URL không trả về file PDF")
    return data


def clean_pdf_text(text: str) -> str:
    # ponytail: decode common PDF font CID/uni glyph escapes; add full CMap parsing if binary stream fonts break
    text = re.sub(r"(?:/|\\)uni([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"(?:/|\\)u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"(?<!\w)uni([0-9a-fA-F]{4})(?!\w)", lambda m: chr(int(m.group(1), 16)), text)
    return unicodedata.normalize("NFC", text)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", clean_pdf_text(value).casefold())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", value.replace("đ", "d")).strip()


def parse_terms(raw: str) -> list[str]:
    terms, seen = [], set()
    for line in raw.splitlines():
        for value in re.split(r"[,;]", line):
            value = re.sub(r"\s+", " ", value).strip()
            key = normalize_text(value)
            if value and key and key not in seen:
                seen.add(key)
                terms.append(value)
    return terms


def term_pattern(term: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(normalize_text(term)) + r"(?!\w)")


def find_matches(text: str, terms: list[str]) -> list[tuple[int, int, str]]:
    matches = []
    for term in terms:
        matches.extend((m.start(), m.end(), term) for m in term_pattern(term).finditer(text))
    chosen = []
    for start, end, term in sorted(matches, key=lambda item: (item[0], -(item[1] - item[0]))):
        if any(start < old_end and end > old_start for old_start, old_end, _ in chosen):
            continue
        chosen.append((start, end, term))
    return chosen


def count_matches(text: str, terms: list[str]) -> int:
    return len(find_matches(text, terms))


def extract_pages(pdf: bytes) -> tuple[int, list[dict]]:
    reader = PdfReader(io.BytesIO(pdf))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        text = clean_pdf_text(re.sub(r"-\s*\n\s*", "", raw))
        text = " ".join(text.split())
        if text:
            pages.append({"page": number, "text": text, "normalized": normalize_text(text)})
    return len(reader.pages), pages


def classify_evidence(name, url, pages_count, pages, erp_terms, tech_terms, context_terms,
                      action_terms, operational_terms, planned_terms, negative_terms) -> dict:
    raw_erp = raw_tech = relevant_erp = relevant_tech = context_hits = 0
    action_hits = operational_hits = planned_hits = negative_hits = word_count = best_score = 0
    relevant_terms, evidence = set(), []
    for page in pages:
        word_count += len(page["text"].split())
        raw_erp += count_matches(page["normalized"], erp_terms)
        raw_tech += count_matches(page["normalized"], tech_terms)
        for unit in re.split(r"(?<=[.!?。！？])\s+", page["text"]):
            unit = clean_pdf_text(unit)
            normalized = normalize_text(unit)
            erp = find_matches(normalized, erp_terms)
            tech = find_matches(normalized, tech_terms)
            context = find_matches(normalized, context_terms)
            if not erp and not tech:
                continue
            is_erp_relevant = bool(erp and context)
            is_tech_relevant = bool(tech and (context or any(
                any(marker in normalize_text(term) for marker in ACCOUNTING_SPECIFIC_MARKERS)
                for _, _, term in tech
            )))
            if not (is_erp_relevant or is_tech_relevant):
                continue
            relevant = (erp if is_erp_relevant else []) + (tech if is_tech_relevant else [])
            relevant_terms.update(term for _, _, term in relevant)
            relevant_erp += len(erp) if is_erp_relevant else 0
            relevant_tech += len(tech) if is_tech_relevant else 0
            context_hits += len(context)
            actions = count_matches(normalized, action_terms)
            operational = count_matches(normalized, operational_terms)
            planned = count_matches(normalized, planned_terms)
            negative = count_matches(normalized, negative_terms)
            action_hits += actions
            operational_hits += operational
            planned_hits += planned
            negative_hits += negative
            if negative:
                status, score = "Phủ định/không áp dụng", 0
            elif operational:
                status, score = "Đã áp dụng/đang vận hành", 4
            elif actions:
                status, score = "Đang triển khai/áp dụng", 3
            elif planned:
                status, score = "Có kế hoạch/dự kiến", 2
            else:
                status, score = "Chỉ đề cập", 1
            best_score = max(best_score, score)
            labels = "; ".join(term for _, _, term in relevant)
            evidence.append(f"Trang {page['page']} | {status} | {labels} | {unit[:700]}")
    statuses = {
        0: "Không có bằng chứng liên quan", 1: "Chỉ đề cập",
        2: "Có kế hoạch/dự kiến", 3: "Đang triển khai/áp dụng",
        4: "Đã áp dụng/đang vận hành",
    }
    return {
        "document": name, "url": url, "pages": pages_count, "word_count": word_count,
        "erp_frequency": raw_erp, "erp_accounting_frequency": relevant_erp,
        "accounting_tech_frequency": raw_tech,
        "accounting_tech_relevant_frequency": relevant_tech,
        "technology_frequency": relevant_erp + relevant_tech,
        "technology_diversity": len(relevant_terms), "accounting_context_hits": context_hits,
        "action_word_hits": action_hits, "operational_evidence_hits": operational_hits,
        "planned_evidence_hits": planned_hits, "negative_evidence_hits": negative_hits,
        "adoption_score": best_score, "adoption_status": statuses[best_score],
        "tech_adoption": int(best_score >= 3), "relevant_terms": "; ".join(sorted(relevant_terms)),
        "evidence": "\n".join(evidence[:20]),
    }


def main() -> None:
    st.set_page_config(page_title="ERP và Công nghệ Kế toán", layout="wide")
    st.title("Phân tích ERP và công nghệ trong kế toán")
    st.caption("Đếm từ khóa theo ngữ cảnh câu, chấm mức áp dụng, giữ số trang PDF và xuất CSV.")

    with st.sidebar:
        st.header("Bộ từ khóa")
        erp_input = st.text_area("Từ khóa ERP", value=DEFAULT_ERP_TERMS, height=230)
        tech_input = st.text_area("Công nghệ kế toán", value=DEFAULT_ACCOUNTING_TECH_TERMS, height=300)
        context_input = st.text_area("Ngữ cảnh kế toán", value=DEFAULT_ACCOUNTING_CONTEXT, height=250)
        action_input = st.text_area("Từ hành động", value=DEFAULT_ACTION_TERMS, height=220)
        operational_input = st.text_area("Từ cho thấy đã vận hành", value=DEFAULT_OPERATIONAL_TERMS, height=170)
        planned_input = st.text_area("Từ cho thấy kế hoạch", value=DEFAULT_PLANNED_TERMS, height=170)
        negative_input = st.text_area("Cụm phủ định", value=DEFAULT_NEGATIVE_TERMS, height=170)
        st.info("ERP/công nghệ chỉ tính liên quan kế toán khi cùng câu có ngữ cảnh kế toán. Câu phủ định không tính là đã áp dụng.")

    links = st.text_area("Link báo cáo PDF", placeholder="Mỗi dòng một URL PDF công khai", height=160)

    if st.button("Phân tích", type="primary"):
        groups = [parse_terms(value) for value in (
            erp_input, tech_input, context_input, action_input,
            operational_input, planned_input, negative_input,
        )]
        erp_terms, tech_terms, context_terms, action_terms, operational_terms, planned_terms, negative_terms = groups
        urls = [line.strip() for line in links.splitlines() if line.strip()]
        if not erp_terms and not tech_terms:
            st.error("Cần ít nhất một từ khóa ERP hoặc công nghệ kế toán.")
        elif not urls:
            st.error("Cần ít nhất một link PDF.")
        else:
            rows = []
            progress = st.progress(0)
            for index, raw_url in enumerate(urls, start=1):
                try:
                    url = public_url(raw_url)
                    page_count, pages = extract_pages(download_pdf(url))
                    row = classify_evidence(
                        url.rsplit("/", 1)[-1] or url, url, page_count, pages,
                        erp_terms, tech_terms, context_terms, action_terms,
                        operational_terms, planned_terms, negative_terms,
                    )
                    rows.append(row)
                    st.success(f"Đã phân tích: {row['document']}")
                except Exception as exc:
                    st.warning(f"Bỏ qua {raw_url}: {exc}")
                progress.progress(index / len(urls))

            if rows:
                st.subheader("Kết quả")
                st.dataframe(rows, use_container_width=True)
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
                st.download_button(
                    "Tải kết quả CSV",
                    output.getvalue().encode("utf-8-sig"),
                    "erp_accounting_technology_analysis.csv",
                    "text/csv",
                )


if __name__ == "__main__":
    main()

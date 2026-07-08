import streamlit as st
import anthropic
import PyPDF2
import docx
import pandas as pd
import io
import json
from datetime import datetime
from deliver_system_prompt import DELIVER_SYSTEM_PROMPT

st.set_page_config(
    page_title="Deliver — Portfolio Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {font-size: 1.1rem; font-weight: 600; color: #1a1a2e;}
    .sub-header {font-size: 0.8rem; color: #6b7280; margin-bottom: 1.5rem;}
    .rag-green {background: #f0fdf4; border-left: 3px solid #22c55e; padding: 0.75rem 1rem; border-radius: 0 8px 8px 0; margin-bottom: 0.75rem;}
    .rag-amber {background: #fff7ed; border-left: 3px solid #f59e0b; padding: 0.75rem 1rem; border-radius: 0 8px 8px 0; margin-bottom: 0.75rem;}
    .rag-red {background: #fef2f2; border-left: 3px solid #ef4444; padding: 0.75rem 1rem; border-radius: 0 8px 8px 0; margin-bottom: 0.75rem;}
    .confidence-high {color: #15803d; font-size: 0.75rem; font-weight: 500;}
    .confidence-med {color: #b45309; font-size: 0.75rem; font-weight: 500;}
    .confidence-low {color: #dc2626; font-size: 0.75rem; font-weight: 500;}
    .doc-uploaded {background: #f0fdf4; border: 0.5px solid #86efac; border-radius: 6px; padding: 6px 10px; font-size: 0.75rem; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;}
    .extraction-note {background: #fafafa; border: 0.5px solid #e5e7eb; border-radius: 6px; padding: 8px 12px; font-size: 0.75rem; color: #6b7280; margin-bottom: 6px;}
</style>
""", unsafe_allow_html=True)

def extract_text_from_pdf(file):
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Could not extract text from PDF: {str(e)}"

def extract_text_from_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    except Exception as e:
        return f"Could not extract text from Word document: {str(e)}"

def extract_text_from_excel(file):
    try:
        xl = pd.ExcelFile(file)
        all_text = []
        for sheet_name in xl.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet_name, header=None)
            all_text.append(f"=== Sheet: {sheet_name} ===")
            all_text.append(df.to_string(index=False, na_rep=''))
        return "\n\n".join(all_text)
    except Exception as e:
        return f"Could not extract from Excel: {str(e)}"

def extract_text_from_csv(file):
    try:
        df = pd.read_csv(file)
        return df.to_string(index=False)
    except Exception as e:
        return f"Could not extract from CSV: {str(e)}"

def extract_document_text(file):
    name = file.name.lower()
    if name.endswith('.pdf'):
        return extract_text_from_pdf(file), "PDF"
    elif name.endswith('.docx'):
        return extract_text_from_docx(file), "Word"
    elif name.endswith(('.xlsx', '.xls')):
        return extract_text_from_excel(file), "Excel"
    elif name.endswith('.csv'):
        return extract_text_from_csv(file), "CSV"
    elif name.endswith('.txt'):
        return file.read().decode('utf-8', errors='ignore'), "Text"
    else:
        return file.read().decode('utf-8', errors='ignore'), "Unknown"

def generate_portfolio_intelligence(documents_content, programme_context):
    client = anthropic.Anthropic()
    
    docs_text = ""
    for doc in documents_content:
        docs_text += f"\n\n{'='*50}\n"
        docs_text += f"DOCUMENT: {doc['name']}\n"
        docs_text += f"TYPE: {doc['type']}\n"
        docs_text += f"CATEGORY: {doc['category']}\n"
        docs_text += f"{'='*50}\n"
        docs_text += doc['content'][:8000]
    
    user_message = f"""
PROGRAMME CONTEXT PROVIDED BY USER:
{programme_context if programme_context else 'No additional context provided.'}

UPLOADED DOCUMENTS:
{docs_text}

Please:
1. Extract structured programme information from all uploaded documents.
2. Reconcile information across documents and flag any inconsistencies.
3. Generate a complete Portfolio Intelligence Record with RAG health assessments, evidence-backed analysis, and management recommendations.
4. Include extraction notes indicating confidence levels and any missing information.

Apply the governing principles throughout — evidence precedes assessment, distinguish performance from constraint, and flag where human review is recommended.
"""
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=DELIVER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text

def ask_followup(intelligence_record, question, documents_content):
    client = anthropic.Anthropic()
    
    docs_summary = "\n".join([f"- {d['name']} ({d['category']})" for d in documents_content])
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=DELIVER_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Portfolio Intelligence Record:\n\n{intelligence_record}\n\nDocuments reviewed:\n{docs_summary}"},
            {"role": "assistant", "content": "I have reviewed the Portfolio Intelligence Record and the underlying documents. What would you like to explore further?"},
            {"role": "user", "content": question}
        ]
    )
    return response.content[0].text

if "documents" not in st.session_state:
    st.session_state.documents = []
if "intelligence_record" not in st.session_state:
    st.session_state.intelligence_record = None
if "conversation" not in st.session_state:
    st.session_state.conversation = []

with st.sidebar:
    st.markdown("**◆ Deliver**")
    st.markdown("<div style='font-size:0.75rem;color:#6b7280;margin-bottom:1rem'>Portfolio Intelligence Platform</div>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.markdown("**Programme context**")
    programme_context = st.text_area(
        "Optional: add context the AI should know",
        placeholder="e.g. This is a Year 3 closure report for an FCDO-funded girls education programme in DRC. Output 2 was affected by road closures in Q4.",
        height=100,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("**Upload documents**")
    
    doc_category = st.selectbox("Document category", [
        "Quarterly narrative report",
        "Budget / financial report",
        "Indicator tracker",
        "Risk register",
        "Workplan",
        "Donor report",
        "Other programme document"
    ])
    
    uploaded_files = st.file_uploader(
        "Upload",
        accept_multiple_files=True,
        type=["pdf", "docx", "xlsx", "xls", "csv", "txt"],
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        if st.button("Add to programme", use_container_width=True):
            for file in uploaded_files:
                content, file_type = extract_document_text(file)
                st.session_state.documents.append({
                    "name": file.name,
                    "type": file_type,
                    "category": doc_category,
                    "content": content,
                    "added": datetime.now().strftime("%H:%M")
                })
            st.success(f"{len(uploaded_files)} document(s) added")
            st.rerun()
    
    if st.session_state.documents:
        st.markdown("---")
        st.markdown(f"**{len(st.session_state.documents)} documents loaded**")
        for doc in st.session_state.documents:
            st.markdown(f"""
            <div class='doc-uploaded'>
                <span>📄</span>
                <div>
                    <div style='font-weight:500;color:#111'>{doc['name'][:35]}</div>
                    <div style='color:#6b7280'>{doc['category']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("Clear all documents", use_container_width=True):
            st.session_state.documents = []
            st.session_state.intelligence_record = None
            st.session_state.conversation = []
            st.rerun()

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown("<div class='main-header'>Deliver — Portfolio Intelligence</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Upload programme documents · AI extracts and interprets · Generate Portfolio Intelligence Record</div>", unsafe_allow_html=True)

if not st.session_state.documents:
    st.info("Upload your programme documents in the sidebar to begin. Deliver accepts narrative reports, budget spreadsheets, indicator trackers, risk registers, and workplans.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style='background:#f8fafc;border:0.5px solid #e2e8f0;border-radius:8px;padding:12px;font-size:0.8rem'>
        <div style='font-weight:500;margin-bottom:6px'>Step 1 — Upload</div>
        <div style='color:#6b7280'>Add your quarterly narrative, budget, indicator tracker, and risk register</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style='background:#f8fafc;border:0.5px solid #e2e8f0;border-radius:8px;padding:12px;font-size:0.8rem'>
        <div style='font-weight:500;margin-bottom:6px'>Step 2 — Generate</div>
        <div style='color:#6b7280'>AI reads across all documents, extracts information, and generates Portfolio Intelligence</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style='background:#f8fafc;border:0.5px solid #e2e8f0;border-radius:8px;padding:12px;font-size:0.8rem'>
        <div style='font-weight:500;margin-bottom:6px'>Step 3 — Review</div>
        <div style='color:#6b7280'>Validate the assessment, add context, ask questions, and export</div>
        </div>
        """, unsafe_allow_html=True)

else:
    if not st.session_state.intelligence_record:
        st.markdown(f"**{len(st.session_state.documents)} documents ready.** Generate Portfolio Intelligence when ready.")
        
        doc_list = ""
        for doc in st.session_state.documents:
            doc_list += f"- {doc['name']} ({doc['category']})\n"
        st.markdown(f"```\n{doc_list}```")
        
        if st.button("Generate Portfolio Intelligence", type="primary", use_container_width=False):
            with st.spinner("Reading documents and generating Portfolio Intelligence... this may take 30-60 seconds"):
                try:
                    result = generate_portfolio_intelligence(
                        st.session_state.documents,
                        programme_context
                    )
                    st.session_state.intelligence_record = result
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating intelligence: {str(e)}")
    
    else:
        tab1, tab2, tab3 = st.tabs(["Portfolio Intelligence Record", "Ask questions", "Export"])
        
        with tab1:
            st.markdown("### Portfolio Intelligence Record")
            st.markdown("*Generated by Deliver · Review and validate before publishing*")
            st.markdown("---")
            st.markdown(st.session_state.intelligence_record)
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Regenerate with updated documents"):
                    st.session_state.intelligence_record = None
                    st.rerun()
            with col2:
                st.download_button(
                    "Download as text",
                    st.session_state.intelligence_record,
                    file_name=f"portfolio_intelligence_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain"
                )
        
        with tab2:
            st.markdown("### Ask about your programme")
            st.markdown("Ask questions about the Portfolio Intelligence Record or request specific analysis.")
            
            for msg in st.session_state.conversation:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
            
            if question := st.chat_input("Ask about the programme, the financial position, specific outputs, risks..."):
                st.session_state.conversation.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)
                
                with st.chat_message("assistant"):
                    with st.spinner("Analysing..."):
                        answer = ask_followup(
                            st.session_state.intelligence_record,
                            question,
                            st.session_state.documents
                        )
                    st.markdown(answer)
                    st.session_state.conversation.append({"role": "assistant", "content": answer})
        
        with tab3:
            st.markdown("### Export")
            st.markdown("Download the Portfolio Intelligence Record for sharing or reporting.")
            
            st.download_button(
                "Download Portfolio Intelligence Record (.txt)",
                st.session_state.intelligence_record,
                file_name=f"portfolio_intelligence_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
            st.markdown("*PDF export and donor report templates coming in Version 2*")

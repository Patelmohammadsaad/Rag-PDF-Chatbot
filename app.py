import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

st.set_page_config(page_title="Chat with PDF (RAG)", page_icon="📄")
st.title("📄 Chat with your PDF")


@st.cache_resource(show_spinner="PDF process ho raha hai...")
def build_vectorstore(pdf_bytes: bytes):
    # 1. Load PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(pdf_bytes)
        path = f.name
    docs = PyPDFLoader(path).load()

    # 2. Chunking
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    # 3. Embeddings (local, free) + 4. ChromaDB
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return Chroma.from_documents(chunks, embeddings)


def answer(vectorstore, question: str):
    # 5. Retrieve top-k similar chunks
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})
    relevant = retriever.invoke(question)
    context = "\n\n".join(d.page_content for d in relevant)

    # 6. Prompt + LLM (Gemini)
    prompt = f"""Answer ONLY from the context below.
If the answer is not in the context, say "Mujhe document mein yeh nahi mila."

Context:
{context}

Question: {question}
Answer:"""

    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0)
    return llm.invoke(prompt).content, relevant
    # resp = llm.invoke(prompt)
    # text = resp.text if hasattr(resp, "text") and isinstance(resp.text, str) else resp.content
    # if isinstance(text, list):
    #  text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    # return text, relevant

uploaded = st.file_uploader("PDF upload karein", type="pdf")

if uploaded:
    vs = build_vectorstore(uploaded.getvalue())
    q = st.text_input("Apna sawal poochhein")
    if q:
        with st.spinner("Soch raha hoon..."):
            ans, sources = answer(vs, q)
        st.subheader("Answer")
        st.write(ans)
        with st.expander("Sources (retrieved chunks)"):
            for s in sources:
                page = s.metadata.get("page")
                st.caption(f"Page {page + 1}" if isinstance(page, int) else "Page ?")
                st.write(s.page_content[:400] + "...")
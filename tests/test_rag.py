import shutil
import uuid
from pathlib import Path

import pytest

from shopmate.domain.messages import MessageType, UserMessage
from shopmate.domain.state import DialogueState
from shopmate.knowledge.providers import RAGProvider
from shopmate.knowledge.rag.embedding import HashingEmbedding
from shopmate.knowledge.rag.loader import load_documents
from shopmate.knowledge.rag.models import DocumentChunk
from shopmate.knowledge.rag.splitter import MarkdownSplitter
from shopmate.knowledge.rag.store import VectorStore

KNOWLEDGE_DIR = (
    Path(__file__).resolve().parents[1] / "docs" / "knowledge"
)
TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def test_splitter_keeps_heading_path():
    text = (
        "# 退款政策\n\n"
        "## 到账时间\n\n"
        "审核通过后按原路退回，支付宝 1-3 个工作日到账。\n"
    )
    chunks = MarkdownSplitter().split(text, source="refund")

    assert len(chunks) == 1
    assert chunks[0].source == "refund"
    assert chunks[0].text.startswith("退款政策 > 到账时间")


def test_splitter_respects_size_and_overlap():
    body = "退款将在审核通过后的一到三个工作日内原路退回。"
    text = "# 退款\n\n## 时效\n\n" + body * 30

    splitter = MarkdownSplitter(chunk_size=120, overlap=20)
    chunks = splitter.split(text, source="refund")

    assert len(chunks) > 1
    heading_length = len("退款 > 时效\n")
    for chunk in chunks:
        assert len(chunk.text) <= 120 + heading_length
    # 相邻片段有重叠，避免语义被切断
    assert chunks[0].text[-10:] in chunks[1].text


@pytest.mark.asyncio
async def test_hashing_embedding_is_deterministic_and_normalized():
    embedding = HashingEmbedding(dim=128)

    first = (await embedding.embed(["退款多久到账"]))[0]
    second = (await embedding.embed(["退款多久到账"]))[0]

    assert first == second
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_store_ranks_relevant_chunk_first():
    embedding = HashingEmbedding(dim=256)
    chunks = [
        DocumentChunk("退款一般 1-3 个工作日原路退回", "refund"),
        DocumentChunk("满 99 元包邮，48 小时内发货", "shipping"),
        DocumentChunk("7 天无理由退货，吊牌需完整", "return"),
    ]
    store = await VectorStore.build(chunks, embedding)

    hits = await store.search("退款多久能到账", embedding, top_k=2)

    assert hits[0].chunk.source == "refund"
    assert hits[0].score > hits[1].score


@pytest.mark.asyncio
async def test_store_save_and_load_roundtrip():
    work_dir = TMP_ROOT / uuid.uuid4().hex
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "index.json"

    try:
        embedding = HashingEmbedding(dim=64)
        store = await VectorStore.build(
            [DocumentChunk("包邮规则：满 99 元包邮", "shipping")],
            embedding,
        )
        store.save(path)

        loaded = VectorStore.load(path, embedding.name)
        assert loaded is not None
        assert loaded.items[0].source == "shipping"

        # 换了模型就不该复用旧索引
        assert VectorStore.load(path, "another-model") is None
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_rag_provider_returns_source_and_score():
    embedding = HashingEmbedding(dim=256)
    store = await VectorStore.build(
        [
            DocumentChunk("退款审核 24 小时内完成", "refund"),
            DocumentChunk("偏远地区需补运费", "shipping"),
        ],
        embedding,
    )
    provider = RAGProvider(
        embedding=embedding,
        store=store,
        top_k=2,
        min_score=0.0,
    )

    chunks = await provider.retrieve(
        DialogueState(sender_id="u1"),
        UserMessage(
            sender_id="u1",
            message_id="m1",
            type=MessageType.TEXT,
            text="退款审核要多久",
        ),
    )

    assert chunks
    assert chunks[0].source == "refund"
    assert chunks[0].score is not None
    assert chunks[0].score > 0


@pytest.mark.asyncio
async def test_rag_provider_falls_back_when_nothing_matches():
    embedding = HashingEmbedding(dim=64)
    store = await VectorStore.build(
        [DocumentChunk("满 99 元包邮", "shipping")],
        embedding,
    )
    provider = RAGProvider(
        embedding=embedding,
        store=store,
        min_score=0.99,
    )

    chunks = await provider.retrieve(
        DialogueState(sender_id="u1"),
        UserMessage(
            sender_id="u1",
            message_id="m1",
            type=MessageType.TEXT,
            text="退款多久到账",
        ),
    )

    assert chunks[0].content == "未检索到相关信息"
    assert chunks[0].source is None


def test_load_documents_reads_all_markdown():
    chunks = load_documents(KNOWLEDGE_DIR)

    assert len(chunks) >= 5
    assert {"refund", "return", "shipping"}.issubset(
        {chunk.source for chunk in chunks}
    )
    assert all(chunk.text.strip() for chunk in chunks)

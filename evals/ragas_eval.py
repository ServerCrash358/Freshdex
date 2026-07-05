import asyncio

import asyncpg
import requests
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from prefect import get_run_logger, task
from prefect.cache_policies import NO_CACHE
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, Faithfulness

from config import Settings
from golden_qa import GOLDEN_SET


async def _seed_golden_corpus(pool: asyncpg.Pool) -> None:
    # Refresh deterministically on every run rather than trying to detect
    # drift -- this eval isn't meant to run every few seconds, so the
    # re-embed cost of a full refresh each run is acceptable.
    titles = [item["title"] for item in GOLDEN_SET]
    await pool.execute("DELETE FROM documents WHERE title = ANY($1::text[])", titles)
    for item in GOLDEN_SET:
        await pool.execute(
            "INSERT INTO documents (title, content) VALUES ($1, $2)",
            item["title"],
            item["content"],
        )


def _query_sync(settings: Settings, question: str) -> tuple[str, list[str]]:
    response = requests.post(
        f"{settings.query_api_url}/query",
        json={"query": question, "top_k": 3, "bypass_cache": True},
        timeout=120,
    )
    response.raise_for_status()
    body = response.json()
    return body["answer"], [r["content"] for r in body["results"]]


def _run_ragas(settings: Settings, samples: list[SingleTurnSample]) -> dict:
    llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.gemini_api_key)
    )
    embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=settings.gemini_api_key)
    )
    dataset = EvaluationDataset(samples=samples)
    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(llm=llm), AnswerRelevancy(llm=llm, embeddings=embeddings)],
    )
    return result.to_pandas().mean(numeric_only=True).to_dict()


def _push_ragas_scores(settings: Settings, scores: dict) -> None:
    registry = CollectorRegistry()
    for name, value in scores.items():
        gauge = Gauge(f"freshdex_ragas_{name}", f"RAGAS {name} score, mean over golden set", registry=registry)
        gauge.set(value)
    push_to_gateway(settings.pushgateway_url, job="freshdex-ragas-eval", registry=registry)


@task(cache_policy=NO_CACHE)
async def run_ragas_eval(settings: Settings, pool: asyncpg.Pool) -> dict:
    logger = get_run_logger()

    await _seed_golden_corpus(pool)
    # Simple settle wait rather than per-question polling (the freshness
    # benchmark task already covers precise polling) -- embedding a handful
    # of short docs finishes well within this window in practice.
    await asyncio.sleep(settings.ragas_corpus_settle_seconds)

    samples = []
    for item in GOLDEN_SET:
        answer, contexts = await asyncio.to_thread(_query_sync, settings, item["question"])
        samples.append(
            SingleTurnSample(
                user_input=item["question"],
                response=answer,
                retrieved_contexts=contexts,
                reference=item["ground_truth"],
            )
        )

    scores = await asyncio.to_thread(_run_ragas, settings, samples)
    logger.info("RAGAS scores: %s", scores)
    _push_ragas_scores(settings, scores)
    return scores

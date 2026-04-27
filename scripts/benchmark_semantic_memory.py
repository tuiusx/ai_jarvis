import argparse
import random
import string
import sys
import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.memory import LongTermMemory


def _random_sentence(rng: random.Random, topic: str):
    suffix = "".join(rng.choices(string.ascii_lowercase + string.digits, k=12))
    return f"Registro sobre {topic} com contexto local {suffix}"


def _percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def run_benchmark(entries=100_000, queries=300, target_p95_ms=300.0, seed=42):
    rng = random.Random(seed)
    topics = ["lampada", "cofre", "garagem", "camera", "rede", "fechadura", "sala", "cozinha"]

    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        semantic_cfg = {
            "enabled": True,
            "model_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "index_path": str(base / "memory_semantic.faiss"),
            "db_path": str(base / "memory_semantic.db"),
            "top_k": 8,
            "response_k": 3,
            "batch_size": 256,
            "mask_sensitive": True,
            "score_threshold": 0.0,
            "hnsw_m": 32,
            "hnsw_ef_search": 128,
        }

        memory = LongTermMemory(file_path=str(base / "memory.json"), limit=max(entries, 200_000), semantic_config=semantic_cfg)
        semantic = memory.semantic_status()
        if not semantic.get("ready"):
            print(f"Benchmark indisponivel: memoria semantica nao pronta ({semantic.get('reason')}).")
            memory.close()
            return 2

        semantic_store = memory.semantic_store
        now = datetime.now().isoformat()
        payload = []
        for idx in range(entries):
            topic = topics[idx % len(topics)]
            payload.append({"text": _random_sentence(rng, topic), "timestamp": now, "type": "general"})

        ingest_start = time.perf_counter()
        inserted = semantic_store.add_entries(payload, batch_size=semantic_cfg["batch_size"])
        ingest_ms = (time.perf_counter() - ingest_start) * 1000.0

        latencies_ms = []
        for _ in range(queries):
            topic = rng.choice(topics)
            query = f"o que voce sabe sobre {topic} da casa"
            started = time.perf_counter()
            semantic_store.search(query, limit=semantic_cfg["top_k"])
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(elapsed_ms)

        p95 = _percentile(latencies_ms, 0.95)
        p50 = _percentile(latencies_ms, 0.50)

        print(
            f"Benchmark semantico | entries={entries} inserted={inserted} queries={queries} "
            f"ingest_ms={ingest_ms:.2f} p50_ms={p50:.2f} p95_ms={p95:.2f} target_p95_ms={target_p95_ms:.2f}"
        )
        if p95 <= target_p95_ms:
            print("Resultado: OK (meta P95 atingida).")
            memory.close()
            return 0

        print("Resultado: FAIL (meta P95 nao atingida).")
        memory.close()
        return 1


def main():
    parser = argparse.ArgumentParser(description="Benchmark sintetico da memoria semantica local.")
    parser.add_argument("--entries", type=int, default=100_000, help="Quantidade de memorias sinteticas.")
    parser.add_argument("--queries", type=int, default=300, help="Quantidade de consultas para medir latencia.")
    parser.add_argument("--target-p95-ms", type=float, default=300.0, help="Meta de latencia P95 em milissegundos.")
    parser.add_argument("--seed", type=int, default=42, help="Seed para reproducibilidade.")
    args = parser.parse_args()

    raise SystemExit(
        run_benchmark(
            entries=args.entries,
            queries=args.queries,
            target_p95_ms=args.target_p95_ms,
            seed=args.seed,
        )
    )


if __name__ == "__main__":
    main()

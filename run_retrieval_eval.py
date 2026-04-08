import argparse
import json
from pathlib import Path
from statistics import mean

from course_rag.services.rag_service import RAGService


def normalize_path(value: str) -> str:
    return str(value or '').replace('\\', '/').strip().lower()


def suffix_match(path_text: str, suffixes: list[str]) -> bool:
    normalized = normalize_path(path_text)
    return any(normalized.endswith(normalize_path(suffix)) for suffix in suffixes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run retrieval evaluation against the course RAG retriever.')
    parser.add_argument('--dataset', default='eval/retrieval_eval_public.json', help='Path to retrieval evaluation dataset JSON.')
    parser.add_argument('--data-dir', default='', help='Override data directory used by RAGService.')
    parser.add_argument('--top-k', type=int, default=0, help='Override top-k used during evaluation.')
    parser.add_argument('--output', default='eval/results/retrieval_eval_latest.json', help='Path to save evaluation report JSON.')
    parser.add_argument('--show-passed', action='store_true', help='Print per-case output for passed cases too.')
    return parser


def evaluate_case(retriever, question: str, expected_suffixes: list[str], top_k: int, min_score: float) -> dict:
    results = retriever.search(question, top_k=top_k, min_score=min_score)
    retrieved = []
    first_hit_rank = None
    for index, result in enumerate(results, start=1):
        path = result.chunk.source_path
        entry = {
            'rank': index,
            'path': path,
            'title': result.chunk.title,
            'score': round(float(result.score), 6),
            'details': result.details,
        }
        retrieved.append(entry)
        if first_hit_rank is None and suffix_match(path, expected_suffixes):
            first_hit_rank = index

    return {
        'retrieved': retrieved,
        'first_hit_rank': first_hit_rank,
        'hit_at_1': first_hit_rank == 1,
        'hit_at_3': first_hit_rank is not None and first_hit_rank <= 3,
        'hit_at_k': first_hit_rank is not None and first_hit_rank <= top_k,
        'mrr': 0.0 if first_hit_rank is None else 1.0 / first_hit_rank,
    }


def main() -> int:
    args = build_parser().parse_args()
    dataset_path = Path(args.dataset)
    dataset = json.loads(dataset_path.read_text(encoding='utf-8'))
    data_dir = args.data_dir or dataset.get('data_dir') or 'data/course'
    top_k = int(args.top_k or dataset.get('default_top_k') or 5)

    service = RAGService(data_dir=data_dir, build_async=False)
    retriever = service.retriever
    if retriever is None:
        raise RuntimeError('retriever not ready')

    min_score = float(service.retrieval_conf['min_score'])
    evaluated_cases = []
    for case in dataset.get('cases', []):
        expected_suffixes = list(case.get('expected_source_suffixes') or [])
        metrics = evaluate_case(retriever, case['question'], expected_suffixes, top_k=top_k, min_score=min_score)
        evaluated_cases.append({
            'id': case['id'],
            'category': case.get('category', ''),
            'question': case['question'],
            'expected_source_suffixes': expected_suffixes,
            'notes': case.get('notes', ''),
            **metrics,
        })

    total = len(evaluated_cases)
    hit_at_1 = sum(1 for case in evaluated_cases if case['hit_at_1'])
    hit_at_3 = sum(1 for case in evaluated_cases if case['hit_at_3'])
    hit_at_k = sum(1 for case in evaluated_cases if case['hit_at_k'])
    mrr = mean([case['mrr'] for case in evaluated_cases]) if evaluated_cases else 0.0

    summary = {
        'dataset': dataset.get('name', dataset_path.stem),
        'data_dir': data_dir,
        'backend': service.index_summary.get('backend'),
        'requested_backend': service.index_summary.get('requested_backend'),
        'documents': service.index_summary.get('documents'),
        'chunks': service.index_summary.get('chunks'),
        'index_cache_hit': service.index_summary.get('index_cache_hit'),
        'bm25_cache_hit': service.index_summary.get('bm25_cache_hit'),
        'vector_sync_stats': service.index_summary.get('vector_sync_stats'),
        'top_k': top_k,
        'total_cases': total,
        'hit_at_1': round(hit_at_1 / total, 4) if total else 0.0,
        'hit_at_3': round(hit_at_3 / total, 4) if total else 0.0,
        'hit_at_k': round(hit_at_k / total, 4) if total else 0.0,
        'mrr': round(mrr, 4),
    }

    output_payload = {
        'summary': summary,
        'cases': evaluated_cases,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print('=== Retrieval Evaluation Summary ===')
    for key, value in summary.items():
        print(f'{key}: {value}')

    print('\n=== Case Results ===')
    for case in evaluated_cases:
        status = 'PASS' if case['hit_at_k'] else 'FAIL'
        if status == 'PASS' and not args.show_passed:
            continue
        print(f"[{status}] {case['id']} | rank={case['first_hit_rank']} | question={case['question']}")
        print(f"  expected={case['expected_source_suffixes']}")
        top_sources = [item['path'] for item in case['retrieved'][:top_k]]
        print(f"  retrieved={top_sources}")

    print(f'\nReport saved to: {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

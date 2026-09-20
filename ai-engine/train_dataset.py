from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.schemas import AnalysisRequest, DetectorOptions
from app.services.pipeline import run_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description='Train and score a dataset assurance model on a dataset directory.')
    parser.add_argument('--source', required=True, help='Dataset root path (directory or .zip archive).')
    parser.add_argument('--name', default='dataset', help='Friendly dataset name for reporting.')
    parser.add_argument('--format', default='AUTO', choices=['AUTO', 'COCO', 'YOLO'], help='Dataset format.')
    parser.add_argument('--folds', type=int, default=2, help='Consensus training folds.')
    parser.add_argument('--batch-size', type=int, default=8, help='Batch size for training.')
    parser.add_argument('--flip-confidence-gap', type=float, default=0.2, help='Label flip confidence threshold.')
    parser.add_argument('--mislabel-min-count', type=int, default=5, help='Minimum image count for mislabel detection.')
    parser.add_argument('--mislabel-min-rate', type=float, default=0.15, help='Minimum mislabel rate.')
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f'Dataset path does not exist: {source}')

    settings = get_settings()
    request = AnalysisRequest(
        source_path=str(source),
        dataset_format=args.format,
        dataset_name=args.name,
        options=DetectorOptions(
            folds=args.folds,
            batch_size=args.batch_size,
            flip_confidence_gap=args.flip_confidence_gap,
            mislabel_min_count=args.mislabel_min_count,
            mislabel_min_rate=args.mislabel_min_rate,
        ),
    )

    result = run_analysis(request, settings=settings)
    print(json.dumps({
        'dataset': result.dataset.model_dump(),
        'trust_score': result.trust_score,
        'risk_level': result.risk_level.value,
        'confidence': result.confidence,
        'components': [c.model_dump() for c in result.component_scores],
        'limitations': result.limitations,
    }, indent=2))


if __name__ == '__main__':
    main()

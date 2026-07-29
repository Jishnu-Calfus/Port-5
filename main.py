"""
Phase 1 pipeline: raw sources -> normalized staging -> LLM-classified
enriched data. Run this end-to-end with `uv run main.py`.
"""
import etl
import classify


def main():
    print("=== Phase 1: ETL (normalize raw sources -> staging) ===")
    etl.main()

    print("\n=== Phase 1: Classification (staging -> enriched) ===")
    classify.main()


if __name__ == "__main__":
    main()

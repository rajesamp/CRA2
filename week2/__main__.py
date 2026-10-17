"""Run one LangGraph assessment, with an optional sanitized MCP trace."""

import argparse
import json

from week2.workflow import respond


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--mode", choices=["Local evidence only", "Groq assessment"],
                        default="Local evidence only")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    answer, trace = respond(args.question, mode=args.mode)
    print(answer)
    if args.trace:
        print(json.dumps(trace, indent=2, allow_nan=False))
    return 1 if trace["status"] in {"unavailable", "tools_unavailable", "retrieval_unavailable"} else 0


if __name__ == "__main__":
    raise SystemExit(main())

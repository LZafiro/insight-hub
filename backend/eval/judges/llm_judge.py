from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class JudgeScore(BaseModel):
    reasoning: str
    score: int = Field(ge=1, le=5)


_FAITHFULNESS_PROMPT = """\
Evaluate whether every factual claim in the answer is supported by the provided context excerpts. \
Claims not found in the context are hallucinations.

Question: {query}

Context:
{context}

Answer: {answer}

Score 1-5:
1 = Most claims are not in the context
2 = Many claims unsupported
3 = About half the claims are supported
4 = Mostly supported, minor unsupported details
5 = Every claim is directly supported by the context

Identify each factual claim in the answer, check it against the context, then give your score."""

_RELEVANCE_PROMPT = """\
Evaluate whether the answer directly addresses the question asked.

Question: {query}

Answer: {answer}

Score 1-5:
1 = Answer ignores the question entirely
2 = Mostly off-topic
3 = Partially addresses the question
4 = Addresses the question well with minor gaps
5 = Directly and completely addresses the question

Analyze, then give your score."""

_CORRECTNESS_PROMPT = """\
Compare the answer to the reference and evaluate factual correctness.

Question: {query}

Reference answer: {reference}

Answer to evaluate: {answer}

Score 1-5:
1 = Contradicts or omits most key facts
2 = Gets few key facts right
3 = Gets about half the key facts right
4 = Mostly correct, minor inaccuracies or gaps
5 = Fully correct, covers all key facts

Identify matching and missing facts, then give your score."""


class LLMJudge:
    def __init__(self, model: str, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def faithfulness(self, query: str, context: str, answer: str) -> JudgeScore:
        return await self._call(
            _FAITHFULNESS_PROMPT.format(query=query, context=context, answer=answer)
        )

    async def relevance(self, query: str, answer: str) -> JudgeScore:
        return await self._call(
            _RELEVANCE_PROMPT.format(query=query, answer=answer)
        )

    async def correctness(self, query: str, answer: str, reference: str) -> JudgeScore:
        return await self._call(
            _CORRECTNESS_PROMPT.format(query=query, answer=answer, reference=reference)
        )

    async def _call(self, prompt: str) -> JudgeScore:
        completion = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a rigorous AI evaluator. Think step by step before assigning a score.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format=JudgeScore,
            temperature=0,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            return JudgeScore(reasoning="Model did not return a structured response.", score=3)
        return parsed

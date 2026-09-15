import { useState } from "react";
import { askQuestion } from "./api";
import { Answer } from "./components/Answer";
import { QuestionForm } from "./components/QuestionForm";
import { SourceList } from "./components/SourceList";
import type { AskResponse } from "./types";
import "./styles.css";

function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleAsk() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isLoading) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await askQuestion({ question: trimmedQuestion });
      setResult(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The request could not be completed.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="hero">
        <p className="eyebrow">Codebase QA V2</p>
        <h1>Ask your repository.</h1>
        <p className="hero-copy">
          A small demonstration of retrieval-grounded answers from a local Python codebase.
        </p>
      </header>

      <QuestionForm
        question={question}
        isLoading={isLoading}
        onQuestionChange={setQuestion}
        onSubmit={handleAsk}
      />

      {isLoading && (
        <div className="status-message loading" role="status">
          Searching the repository and generating an answer…
        </div>
      )}

      {error && (
        <div className="status-message error" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="result-stack">
          <Answer answer={result.answer} />
          <SourceList sources={result.sources} />
        </div>
      )}
    </main>
  );
}

export default App;

import ReactMarkdown from "react-markdown";

interface AnswerProps {
  answer: string;
}

export function Answer({ answer }: AnswerProps) {
  return (
    <section className="answer-panel" aria-labelledby="answer-heading">
      <div className="section-heading">
        <p className="eyebrow">Response</p>
        <h2 id="answer-heading">Answer</h2>
      </div>
      <div className="answer-markdown">
        <ReactMarkdown>{answer}</ReactMarkdown>
      </div>
    </section>
  );
}

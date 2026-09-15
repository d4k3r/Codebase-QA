import type { FormEvent } from "react";

interface QuestionFormProps {
  question: string;
  isLoading: boolean;
  onQuestionChange: (question: string) => void;
  onSubmit: () => void;
}

export function QuestionForm({
  question,
  isLoading,
  onQuestionChange,
  onSubmit,
}: QuestionFormProps) {
  const isEmpty = question.trim().length === 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isLoading && !isEmpty) {
      onSubmit();
    }
  }

  return (
    <form className="question-form" onSubmit={handleSubmit}>
      <label htmlFor="question">Ask about the indexed repository</label>
      <textarea
        id="question"
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="Where is configuration loaded?"
        rows={4}
        disabled={isLoading}
      />
      <div className="form-footer">
        <span className="form-hint">Questions are answered from retrieved repository context.</span>
        <button type="submit" disabled={isLoading || isEmpty}>
          {isLoading ? "Asking…" : "Ask repository"}
        </button>
      </div>
    </form>
  );
}

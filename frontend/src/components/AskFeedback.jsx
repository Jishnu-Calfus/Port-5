import { useState } from "react";
import { askQuestion } from "../api";

export default function AskFeedback() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleAsk() {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await askQuestion(question);
      setAnswer(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <div className="section-title">Ask Your Feedback</div>
      <div className="ask-box">
        <input
          type="text"
          placeholder="e.g. why are people unhappy with customer support?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
        />
        <button onClick={handleAsk} disabled={loading}>
          {loading ? "Asking..." : "Ask"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {answer && (
        <div>
          <p className="ask-answer">{answer.answer}</p>
          {answer.cited_ids.length > 0 && (
            <div className="cited-ids">
              {answer.cited_ids.map((id) => (
                <span className="cited-id-chip" key={id}>
                  feedback #{id}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

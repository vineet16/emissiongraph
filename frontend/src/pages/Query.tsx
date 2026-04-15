import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { queryLLM } from "../api";

interface Message {
  role: "user" | "assistant";
  content: string;
  context?: string[];
}

const SUGGESTIONS = [
  "Which port has the highest emission intensity and why?",
  "Compare Scope 1 vs Scope 2 emissions across all ports",
  "Which port handles the most cargo but has the lowest emissions?",
  "What are the top 3 emission sources across the fleet?",
  "Summarize the fleet emissions for FY24-25",
];

export default function Query() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [fy, setFy] = useState("FY24-25");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(question?: string) {
    const q = question || input.trim();
    if (!q) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res = await queryLLM(q, fy);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, context: res.context_used },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate("/")}
            className="text-gray-400 hover:text-white"
          >
            &larr; Dashboard
          </button>
          <h1 className="text-lg font-bold">Ask about Emissions</h1>
        </div>
        <select
          value={fy}
          onChange={(e) => setFy(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm"
        >
          <option value="FY24-25">FY24-25</option>
          <option value="FY23-24">FY23-24</option>
        </select>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-4xl mx-auto w-full">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <h2 className="text-xl font-medium text-gray-400 mb-6">
              Ask any question about your port emissions data
            </h2>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(s)}
                  className="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-sm text-gray-300 hover:bg-gray-700 hover:text-white text-left"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 border border-gray-700 text-gray-200"
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.context && (
                <div className="mt-2 pt-2 border-t border-gray-600 text-xs text-gray-400">
                  Data from: {msg.context.join(", ")}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-400">
              Analyzing emissions data...
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 bg-gray-900 p-4">
        <div className="max-w-4xl mx-auto flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && handleSend()}
            placeholder="Ask about emissions, intensity, sources..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
            disabled={loading}
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

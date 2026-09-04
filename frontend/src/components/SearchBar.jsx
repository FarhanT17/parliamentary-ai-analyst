 import { useState, useRef, useEffect } from 'react';

const SearchBar = ({ onSearch, loading, suggestions }) => {
  const [query, setQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
      setShowSuggestions(false);
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    onSearch(suggestion);
  };

  const suggestedQuestions = [
    "What is the role of the Prime Minister?",
    "How does Parliament make laws?",
    "What is the UK's approach to climate change?",
    "How does the NHS work?",
    "What is the House of Commons?",
    "What are the UK's immigration policies?",
    "How is the economy doing?",
    "What is the Brexit agreement?",
  ];

  return (
    <div className="w-full max-w-3xl mx-auto">
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative flex items-center gap-3">
          <div className="relative flex-1">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" 
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
            <input
              ref={inputRef}
              type="text"
              placeholder="Ask about UK Parliament, legislation, or government..."
              className="w-full pl-12 pr-4 py-4 text-lg border-2 border-gray-200 rounded-xl 
                       focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10 
                       transition-all shadow-sm hover:shadow-md"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setShowSuggestions(e.target.value.length > 0);
              }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              disabled={loading}
            />
          </div>
          <button
            type="submit"
            className="px-8 py-4 bg-primary text-white rounded-xl font-semibold 
                     hover:bg-primary/90 transition-all disabled:opacity-50 
                     disabled:cursor-not-allowed shadow-md hover:shadow-lg 
                     whitespace-nowrap"
            disabled={loading || !query.trim()}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Thinking...
              </span>
            ) : (
              'Ask'
            )}
          </button>
        </div>

        {showSuggestions && !loading && (
          <div className="absolute z-10 w-full mt-2 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden animate-fade-in">
            <div className="p-2">
              <p className="text-xs text-gray-400 px-3 py-1">Suggested questions:</p>
              {suggestedQuestions.map((sq, index) => (
                <button
                  key={index}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 
                           text-gray-700 text-sm transition-colors flex items-center gap-2"
                  onClick={() => handleSuggestionClick(sq)}
                >
                  <span className="text-primary">•</span>
                  {sq}
                </button>
              ))}
            </div>
          </div>
        )}
      </form>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-3 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 bg-blue-500 rounded-full"></span>
          Hansard Debates
        </span>
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
          Legislation
        </span>
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 bg-yellow-500 rounded-full"></span>
          Parliamentary Questions
        </span>
        <span className="text-gray-300">|</span>
        <span className="text-gray-400">AI-powered RAG system</span>
      </div>
    </div>
  );
};

export default SearchBar;
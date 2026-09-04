import { useState } from 'react';

const ResultCard = ({ answer, sources, evidence_count, is_sample, is_demo, loading }) => {
  const [copied, setCopied] = useState(false);

  if (loading) {
    return (
      <div className="w-full max-w-3xl mx-auto mt-8 animate-pulse">
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
          <div className="h-6 bg-gray-200 rounded w-3/4 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-5/6 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-4/6"></div>
        </div>
      </div>
    );
  }

  if (!answer) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const cleanAnswer = answer
    .replace(/\{[^{}]*\}/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  const deduplicateSources = (sourceList) => {
    if (!sourceList) return [];
    const seen = new Set();
    const unique = [];
    sourceList.forEach(source => {
      const key = source.title || source.url || source.snippet || source.type || '';
      const cleanKey = key.toLowerCase().trim();
      if (!seen.has(cleanKey) && cleanKey) {
        seen.add(cleanKey);
        unique.push(source);
      }
    });
    return unique;
  };

  const uniqueSources = deduplicateSources(sources);
  const displayCount = uniqueSources.length;

  return (
    <div className="w-full max-w-3xl mx-auto mt-8 animate-slide-up">
      <div className="bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden">
        <div className="bg-gradient-to-r from-primary/5 to-transparent px-6 py-4 border-b border-gray-100">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="bg-primary/10 p-2 rounded-lg">
                <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" 
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <span className="font-semibold text-gray-700">Answer</span>
              {displayCount > 0 && (
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                  Grounded in {displayCount} source{displayCount > 1 ? 's' : ''}
                </span>
              )}
              {is_demo && (
                <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                  📚 Knowledge Base
                </span>
              )}
              {is_sample && (
                <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
                  Sample data
                </span>
              )}
            </div>
            <button
              onClick={handleCopy}
              className="text-gray-400 hover:text-primary transition-colors text-sm flex items-center gap-1"
            >
              {copied ? (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                  Copied!
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" 
                      d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy
                </>
              )}
            </button>
          </div>
        </div>

        <div className="px-6 py-5">
          <p className="text-gray-800 text-lg leading-relaxed whitespace-pre-wrap">{cleanAnswer}</p>
        </div>

        {uniqueSources && uniqueSources.length > 0 && (
          <div className="bg-gray-50 px-6 py-4 border-t border-gray-100">
            <div className="flex items-center gap-2 mb-2">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" 
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm font-medium text-gray-600">
                Sources ({displayCount})
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {uniqueSources.map((source, index) => {
                const displayName = source.type || source.source || source.title || `Source ${index + 1}`;
                const sourceType = source.source || source.type || '';
                let colorClass = 'bg-gray-100 text-gray-700';
                
                if (sourceType === 'demo' || source.is_sample) {
                  colorClass = 'bg-yellow-100 text-yellow-700';
                } else if (sourceType.includes('hansard') || sourceType === 'hansard') {
                  colorClass = 'bg-blue-100 text-blue-700';
                } else if (sourceType === 'legislation' || sourceType.includes('legislation')) {
                  colorClass = 'bg-green-100 text-green-700';
                } else if (sourceType.includes('question') || sourceType.includes('questions')) {
                  colorClass = 'bg-purple-100 text-purple-700';
                } else if (sourceType.includes('research') || sourceType === 'research_briefings') {
                  colorClass = 'bg-indigo-100 text-indigo-700';
                } else if (sourceType.includes('members') || sourceType === 'members') {
                  colorClass = 'bg-pink-100 text-pink-700';
                } else if (sourceType.includes('election')) {
                  colorClass = 'bg-orange-100 text-orange-700';
                }
                
                return (
                  <a
                    key={index}
                    href={source.url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`text-xs px-3 py-1 rounded-full ${colorClass} hover:opacity-80 transition-opacity ${source.url ? 'cursor-pointer hover:shadow-md' : 'cursor-default'}`}
                  >
                    {source.title || displayName}
                    {source.url && ' ↗'}
                  </a>
                );
              })}
            </div>
          </div>
        )}

        <div className="px-6 py-3 bg-gray-50/50 border-t border-gray-100 flex flex-wrap justify-between items-center text-xs text-gray-400 gap-2">
          <span>Generated by Parliamentary AI Analyst</span>
          <span>UK Parliament Hackathon 2026</span>
        </div>
      </div>
    </div>
  );
};

export default ResultCard;
import { useState, useEffect } from 'react';
import Header from './components/Header';
import Footer from './components/Footer';
import SearchBar from './components/SearchBar';
import ResultCard from './components/ResultCard';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isOnline, setIsOnline] = useState(false);
  const [stats, setStats] = useState({
    questionsAsked: 0,
    retrievedSources: 0,
    liveDocuments: 0,
    totalDocuments: 0
  });

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await axios.get(`${API_URL}/health`);
        setIsOnline(response.data.status === 'healthy');
      } catch {
        setIsOnline(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleSearch = async (query) => {
    setLoading(true);
    setError(null);
    setAnswer(null);

    try {
      const response = await axios.post(`${API_URL}/ask`, { query });
      
      setAnswer(response.data);
      
      if (response.data.data_status) {
        setStats(prev => ({
          ...prev,
          questionsAsked: prev.questionsAsked + 1,
          retrievedSources: response.data.evidence_count || 0,
          liveDocuments: response.data.data_status.live_documents || 0,
          totalDocuments: response.data.data_status.total_documents || 0
        }));
      } else {
        setStats(prev => ({
          ...prev,
          questionsAsked: prev.questionsAsked + 1
        }));
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-blue-50 via-gray-50 to-white">
      <Header isOnline={isOnline} />

      <main className="flex-1 container mx-auto px-4 py-8 max-w-6xl">
        <section className="text-center mb-10 animate-fade-in">
          <div className="inline-block mb-4 px-4 py-1.5 bg-primary/10 text-primary text-sm font-medium rounded-full">
            🏛️ UK Parliament Hackathon 2026
          </div>
          <h2 className="text-4xl md:text-5xl font-bold text-gray-800 mb-4">
            Ask About UK Parliament
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            AI-powered Q&A system that makes parliamentary debates, legislation, 
            and government data accessible through natural language.
          </p>
        </section>

        <div className="flex flex-wrap justify-center gap-6 mb-8 text-sm">
          <div className="flex items-center gap-2 bg-white/70 backdrop-blur-sm px-4 py-2 rounded-lg shadow-sm">
            <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-gray-600">Status: {isOnline ? 'Online' : 'Offline'}</span>
          </div>
          <div className="flex items-center gap-2 bg-white/70 backdrop-blur-sm px-4 py-2 rounded-lg shadow-sm">
            <span className="font-semibold text-primary">{stats.retrievedSources}</span>
            <span className="text-gray-600">Retrieved Sources</span>
          </div>
          <div className="flex items-center gap-2 bg-white/70 backdrop-blur-sm px-4 py-2 rounded-lg shadow-sm">
            <span className="font-semibold text-primary">{stats.liveDocuments}</span>
            <span className="text-gray-600">Live Documents</span>
          </div>
          <div className="flex items-center gap-2 bg-white/70 backdrop-blur-sm px-4 py-2 rounded-lg shadow-sm">
            <span className="font-semibold text-primary">{stats.questionsAsked}</span>
            <span className="text-gray-600">Questions Asked</span>
          </div>
        </div>

        <div className="glass-effect rounded-2xl shadow-xl p-6 md:p-8 border border-white/50">
          <SearchBar onSearch={handleSearch} loading={loading} />
        </div>

        {error && (
          <div className="mt-6 max-w-3xl mx-auto animate-fade-in">
            <div className="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-xl">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <p className="font-medium">Error</p>
                  <p className="text-sm">{error}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <ResultCard 
          answer={answer?.answer} 
          sources={answer?.sources} 
          evidence_count={answer?.evidence_count}
          is_sample={answer?.is_sample_data}
          is_demo={answer?.is_demo_answer}
          loading={loading}
        />

        {answer?.is_sample_data && (
          <div className="mt-4 max-w-3xl mx-auto text-center">
            <p className="text-sm text-gray-400">
              💡 Sample data mode. For full RAG capabilities with real parliamentary data, 
              connect to the complete backend with official UK Parliament APIs.
            </p>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}

export default App;
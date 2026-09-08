const Header = ({ isOnline }) => {
  return (
    <header className="bg-primary text-white shadow-lg">
      <div className="container mx-auto px-4 py-4 md:py-6 max-w-6xl">
        <div className="flex items-center justify-between flex-wrap gap-3 md:gap-4">
          {/* Logo and Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 md:w-12 md:h-12 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm flex-shrink-0">
              <svg className="w-6 h-6 md:w-8 md:h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" 
                  d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div>
              <h1 className="text-base md:text-2xl font-bold tracking-tight leading-tight">
                Parliamentary AI Analyst
              </h1>
              <p className="text-[10px] md:text-sm text-white/70 flex items-center gap-1.5">
                UK Parliament Hackathon 2026
                <span className="hidden sm:inline-block w-1 h-1 bg-white/30 rounded-full"></span>
                <span className="hidden sm:inline text-white/50">v3.0.0</span>
              </p>
            </div>
          </div>

          {/* Right side - GitHub + Status */}
          <div className="flex items-center gap-2 md:gap-4">
            {/* GitHub Link */}
            <a 
              href="https://github.com/FarhanT17/parliamentary-ai-analyst"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white/70 hover:text-white transition-all duration-300 hover:scale-110"
              aria-label="GitHub Repository"
            >
              <svg className="w-5 h-5 md:w-6 md:h-6" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.03-2.682-.103-.253-.447-1.27.098-2.646 0 0 .84-.269 2.75 1.025.8-.223 1.65-.334 2.5-.334.85 0 1.7.111 2.5.334 1.91-1.294 2.75-1.025 2.75-1.025.545 1.376.201 2.393.099 2.646.64.698 1.03 1.591 1.03 2.682 0 3.841-2.337 4.687-4.565 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
              </svg>
            </a>

            {/* Status Indicator - Clean version */}
            <div className={`flex items-center gap-1.5 md:gap-2 px-2.5 py-1.5 md:px-4 md:py-2 rounded-lg backdrop-blur-sm border border-white/10 ${
              isOnline ? 'bg-green-500/20' : 'bg-red-500/20'
            }`}>
              <span className={`relative flex h-2.5 w-2.5 md:h-3 md:w-3`}>
                <span className={`absolute inline-flex h-full w-full rounded-full ${
                  isOnline ? 'bg-green-400' : 'bg-red-400'
                } opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 md:h-3 md:w-3 ${
                  isOnline ? 'bg-green-500' : 'bg-red-500'
                }`}></span>
              </span>
              <span className="text-[10px] md:text-sm font-medium tracking-wide text-white">
                {isOnline ? 'Live' : 'Offline'}
              </span>
            </div>

            {/* Hackathon badge - only visible on larger screens */}
            <div className="hidden lg:flex items-center gap-1.5 bg-white/10 px-3 py-1.5 rounded-lg border border-white/5">
              <span className="text-[10px] font-medium text-white/80">🏛️ Hackathon</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
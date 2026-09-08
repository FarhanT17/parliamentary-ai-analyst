const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-white/80 backdrop-blur-sm border-t border-gray-200 mt-auto">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          {/* Left side - Copyright and Hackathon badge */}
          <div className="flex flex-wrap items-center justify-center gap-4">
            <span className="text-sm text-gray-600">
              © {currentYear} Parliamentary AI Analyst
            </span>
            <span className="text-gray-300 hidden sm:inline">|</span>
            <span className="text-sm text-gray-500 flex items-center gap-2">
              Built for
              <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-primary/10 text-primary rounded-full text-xs font-medium">
                🏛️ UK Parliament Hackathon 2026
              </span>
            </span>
          </div>

          {/* Right side - Data source and GitHub */}
          <div className="flex flex-wrap items-center justify-center gap-4 md:gap-6 text-sm text-gray-500">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-blue-500 rounded-full inline-block animate-pulse"></span>
              Data: UK Parliament parliamentary records
            </span>
            
            {/* Version badge */}
            <span className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full text-[10px] font-mono border border-gray-200">
              v3.0.0
            </span>

            <a
              href="https://github.com/FarhanT17/parliamentary-ai-analyst"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 hover:text-primary transition-colors group"
            >
              <svg 
                className="w-4 h-4 transition-colors group-hover:text-primary" 
                fill="currentColor" 
                viewBox="0 0 24 24"
              >
                <path fillRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.03-2.682-.103-.253-.447-1.27.098-2.646 0 0 .84-.269 2.75 1.025.8-.223 1.65-.334 2.5-.334.85 0 1.7.111 2.5.334 1.91-1.294 2.75-1.025 2.75-1.025.545 1.376.201 2.393.099 2.646.64.698 1.03 1.591 1.03 2.682 0 3.841-2.337 4.687-4.565 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
              </svg>
              <span>GitHub</span>
              <svg 
                className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" 
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          </div>
        </div>

        {/* Bottom bar with status and license */}
        <div className="mt-4 pt-4 border-t border-gray-100 flex flex-col sm:flex-row justify-between items-center gap-2 text-[10px] text-gray-400">
          <div className="flex items-center gap-3">
            <span>Open source under Apache 2.0</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full"></span>
              All data from official sources
            </span>
            <span className="text-gray-300 hidden sm:inline">|</span>
            <a 
              href="/privacy" 
              className="hover:text-gray-600 transition-colors"
            >
              Privacy
            </a>
            <a 
              href="/terms" 
              className="hover:text-gray-600 transition-colors"
            >
              Terms
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
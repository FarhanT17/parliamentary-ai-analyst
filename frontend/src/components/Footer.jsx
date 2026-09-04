const Footer = () => {
  const currentYear = new Date().getFullYear();
  
  return (
    <footer className="bg-white/80 backdrop-blur-sm border-t border-gray-200 mt-auto">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">
              © {currentYear} Parliamentary AI Analyst
            </span>
            <span className="text-gray-300">|</span>
            <span className="text-sm text-gray-500">
              Built for UK Parliament Hackathon
            </span>
          </div>
          <div className="flex items-center gap-6 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-blue-500 rounded-full inline-block"></span>
              Data: UK Parliament parliamentary records
            </span>
            <a 
              href="https://github.com/FarhanT17/parliamentary-ai-analyst"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              GitHub
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
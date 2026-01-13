// ngrok Configuration Helper
// This file helps configure the backend API URL when using ngrok

(function() {
  // Check if we're on ngrok
  const isNgrok = window.location.hostname.includes('ngrok');
  const isHttps = window.location.protocol === 'https:';
  
  if (isNgrok || isHttps) {
    // Check if backend URL is already configured
    const backendUrl = localStorage.getItem('backend_ngrok_url');
    
    if (!backendUrl) {
      console.log('%c⚠️ ngrok Backend Configuration Required', 'color: orange; font-size: 16px; font-weight: bold;');
      console.log('%cYour frontend is running on HTTPS/ngrok, but the backend API URL is not configured.', 'color: orange;');
      console.log('%cTo fix this:', 'color: orange; font-weight: bold;');
      console.log('1. Start ngrok for your Django backend: ngrok http 8000');
      console.log('2. Copy the HTTPS URL (e.g., https://xxxxx.ngrok-free.app)');
      console.log('3. Run this in the browser console:');
      console.log('   localStorage.setItem("backend_ngrok_url", "https://xxxxx.ngrok-free.app");');
      console.log('4. Refresh the page');
      console.log('');
      console.log('Or set the REACT_APP_API_URL environment variable before building.');
    } else {
      console.log(`%c✓ Backend API URL configured: ${backendUrl}`, 'color: green;');
      window.REACT_APP_API_URL = `${backendUrl}/api`;
    }
  }
})();


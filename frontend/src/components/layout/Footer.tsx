import { Link } from '@tanstack/react-router';
import { useState } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';

function FacebookIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-label="Facebook"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" /></svg>
  );
}

function InstagramIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="Instagram">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function YoutubeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-label="YouTube">
      <path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.97C18.88 4 12 4 12 4s-6.88 0-8.59.45A2.78 2.78 0 0 0 1.46 6.42 29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58 2.78 2.78 0 0 0 1.95 1.97C5.12 20 12 20 12 20s6.88 0 8.59-.45a2.78 2.78 0 0 0 1.95-1.97A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z" /><polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02" fill="white" />
    </svg>
  );
}

export function Footer() {
  const [expanded, setExpanded] = useState(false);

  return (
    <footer className="site-footer !pt-0 !pb-0 transition-all duration-300" role="contentinfo">
      {/* Compact Bar */}
      <div 
        className="w-full flex items-center justify-between px-4 lg:px-8 py-4 bg-[#0a0f1a] cursor-pointer hover:bg-black transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <p className="text-sm font-medium text-white/70">
          &copy; {new Date().getFullYear()} Al-Aqsa Computers. All rights reserved.
        </p>
        <button className="flex items-center gap-2 text-sm font-bold text-white hover:text-[#1a73e8] transition-colors">
          {expanded ? "Hide Footer" : "Expand Footer"}
          {expanded ? <ChevronDown className="h-5 w-5" /> : <ChevronUp className="h-5 w-5" />}
        </button>
      </div>

      <div className={`overflow-hidden transition-all duration-500 ease-in-out ${expanded ? 'max-h-[800px] opacity-100 pb-12' : 'max-h-0 opacity-0'}`}>
        <div className="footer-inner pt-8">
          {/* Column 1: Brand */}
          <div className="footer-col">
            <div className="footer-logo mb-6">
              <img src="https://alaqsa.com.pk/wp-content/uploads/2021/06/logo-11-1.png" alt="Al-Aqsa Computers" className="h-14 w-auto brightness-0 invert" />
            </div>
            <p className="footer-tagline">
              Lahore's trusted source for laptops, accessories, and electronics since 2005.
            </p>
            <div className="footer-social">
              <a href="https://www.facebook.com/aacomp" className="footer-social-icon" target="_blank" rel="noopener noreferrer" aria-label="Facebook">
                <FacebookIcon />
              </a>
              <a href="https://www.youtube.com/@al_aqsa1995" className="footer-social-icon" target="_blank" rel="noopener noreferrer" aria-label="YouTube">
                <YoutubeIcon />
              </a>
              <a href="https://www.instagram.com/al_aqsa_computers/" className="footer-social-icon" target="_blank" rel="noopener noreferrer" aria-label="Instagram">
                <InstagramIcon />
              </a>
            </div>
          </div>

          {/* Column 2: Quick links */}
          <div className="footer-col">
            <h3 className="footer-col-heading">Quick Links</h3>
            <ul className="footer-links">
              <li><Link to="/" className="footer-link">Home</Link></li>
              <li><Link to="/" search={{ category: "New Laptops" }} className="footer-link">New Laptops</Link></li>
              <li><Link to="/" search={{ category: "Used Laptops" }} className="footer-link">Used Laptops</Link></li>
              <li><Link to="/" search={{ category: "Accessories" }} className="footer-link">Accessories</Link></li>
              <li><Link to="/" search={{ category: "Smart Gadgets" }} className="footer-link">Smart Gadgets</Link></li>
              <li><Link to="/" search={{ category: "Top Brands" }} className="footer-link">Top Brands</Link></li>
            </ul>
          </div>

          {/* Column 3: Contact */}
          <div className="footer-col">
            <h3 className="footer-col-heading">Contact Us</h3>
            <address className="footer-address">
              <p>T-7, 3rd Floor, Zaitoon Plaza,</p>
              <p>Hall Road, Lahore, Pakistan</p>
            </address>
            <ul className="footer-contact-list">
              <li><a href="tel:+924237120011" className="footer-contact-link">Laptop: +92 42 37120011</a></li>
              <li><a href="tel:+924237320887" className="footer-contact-link">Desktop: +92 42 37320887</a></li>
              <li><a href="https://wa.me/923367120011" className="footer-contact-link">WhatsApp: +92 336 712 0011</a></li>
              <li><a href="mailto:maqbool@alaqsa.com.pk" className="footer-contact-link">maqbool@alaqsa.com.pk</a></li>
            </ul>
          </div>
        </div>
      </div>
    </footer>
  );
}

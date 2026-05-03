import { Link, useNavigate } from "@tanstack/react-router";
import { Search, Sparkles, ChevronDown, ChevronRight } from "lucide-react";
import { categoryTree } from "@/data/categories";
import type { CategoryTree } from "@/types/product";

interface Props {
  search: string;
  onSearch: (q: string) => void;
  aiActive: boolean;
  onAiToggle: () => void;
}

// Al-Aqsa Blue Triangle Logo (SVG recreated from original branding)
function AlAqsaLogo({ size = 52 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Al-Aqsa Computers logo mark">
      <polygon points="26,2 50,48 2,48" fill="#1a73e8" />
      <polygon points="26,14 42,44 10,44" fill="#0d5cbf" opacity="0.6" />
      <polygon points="26,24 36,42 16,42" fill="white" opacity="0.9" />
    </svg>
  );
}

// Social icon components
function FacebookIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-label="Facebook">
      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
    </svg>
  );
}

function YoutubeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-label="YouTube">
      <path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.97C18.88 4 12 4 12 4s-6.88 0-8.59.45A2.78 2.78 0 0 0 1.46 6.42 29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58 2.78 2.78 0 0 0 1.95 1.97C5.12 20 12 20 12 20s6.88 0 8.59-.45a2.78 2.78 0 0 0 1.95-1.97A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z" />
      <polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02" fill="white" />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="Instagram">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-label="WhatsApp">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
      <path d="M12 0C5.374 0 0 5.373 0 12c0 2.117.554 4.133 1.521 5.872L.057 23.98l6.304-1.654A11.935 11.935 0 0 0 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.816 9.816 0 0 1-5.001-1.371l-.359-.214-3.717.975.993-3.618-.235-.372A9.817 9.817 0 0 1 2.182 12C2.182 6.574 6.574 2.182 12 2.182S21.818 6.574 21.818 12 17.426 21.818 12 21.818z" />
    </svg>
  );
}

function EmailIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="Email">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}

function LaptopIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="Laptop">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="0" y1="21" x2="24" y2="21" />
    </svg>
  );
}

function DesktopIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-label="Desktop">
      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

// Render nested dropdown recursively
function NavDropdownItem({ item, parentCategory }: { item: string | CategoryTree, parentCategory?: string }) {
  const isString = typeof item === 'string';
  const name = isString ? item : item.name;
  
  // We determine the query params based on depth.
  // For simplicity, navigating to a subcategory searches within its parent.
  const searchParams = parentCategory 
    ? { category: parentCategory, subcategory: name } 
    : { category: name };

  if (isString || !item.subcategories || item.subcategories.length === 0) {
    return (
      <Link 
        to="/" 
        search={searchParams}
        className="block px-4 py-2.5 text-sm text-foreground hover:bg-[#1a73e8] hover:text-white transition-colors"
      >
        {name}
      </Link>
    );
  }

  // It has subcategories, render a drop-right menu
  return (
    <div className="group/sub relative">
      <Link 
        to="/" 
        search={searchParams}
        className="flex items-center justify-between px-4 py-2.5 text-sm text-foreground hover:bg-[#1a73e8] hover:text-white transition-colors cursor-pointer"
      >
        {name}
        <ChevronRight className="h-4 w-4 opacity-50" />
      </Link>
      
      {/* Sub-dropdown (Drop-right) */}
      <div className="absolute left-full top-0 hidden w-56 flex-col bg-white shadow-xl border border-border py-2 group-hover/sub:flex z-[60] ml-[-1px]">
        {item.subcategories.map((sub, idx) => (
          <NavDropdownItem key={idx} item={sub} parentCategory={name} />
        ))}
      </div>
    </div>
  );
}

export function Navbar({ search, onSearch, aiActive, onAiToggle }: Props) {
  return (
    <header className="sticky top-0 z-50" role="banner">

      {/* ── Tier 1: Notice bar ─────────────────────────────────────── */}
      <div className="header-notice-bar">
        <p className="header-notice-text">
          Due to Government Notification, All Cash on Delivery (COD) orders will be charged&nbsp;
          <strong className="header-notice-highlight">4% tax</strong>
        </p>
      </div>

      {/* ── Tier 2: Contact bar ───────────────────────────────────── */}
      <div className="header-contact-bar">
        <div className="header-contact-inner">
          {/* Left: contact details */}
          <div className="header-contact-details">
            <a href="tel:+924237120011" className="header-contact-item" aria-label="Call laptop section">
              <LaptopIcon />
              <span>Laptop Section: +92 42 37120011</span>
            </a>
            <a href="tel:+924237320887" className="header-contact-item" aria-label="Call desktop section">
              <DesktopIcon />
              <span>Desktop Section: +92 42 37320887</span>
            </a>
            <a href="https://wa.me/923367120011" className="header-contact-item" aria-label="WhatsApp us" target="_blank" rel="noopener noreferrer">
              <WhatsAppIcon />
              <span>WhatsApp: +92 0336 712 0011</span>
            </a>
            <a href="mailto:maqbool@alaqsa.com.pk" className="header-contact-item" aria-label="Email us">
              <EmailIcon />
              <span>maqbool@alaqsa.com.pk</span>
            </a>
          </div>

          {/* Right: social icons */}
          <div className="header-social-icons">
            <a href="https://www.facebook.com/aacomp" className="header-social-icon" target="_blank" rel="noopener noreferrer" aria-label="Facebook page">
              <FacebookIcon />
            </a>
            <a href="https://www.youtube.com/@al_aqsa1995" className="header-social-icon" target="_blank" rel="noopener noreferrer" aria-label="YouTube channel">
              <YoutubeIcon />
            </a>
            <a href="https://www.instagram.com/al_aqsa_computers/" className="header-social-icon" target="_blank" rel="noopener noreferrer" aria-label="Instagram page">
              <InstagramIcon />
            </a>
          </div>
        </div>
      </div>

      {/* ── Tier 3: Main header ──────────────────────────────────────── */}
      <div className="header-main-bar">
        <div className="header-main-inner">
          {/* Logo */}
          <Link to="/" className="header-logo-link" aria-label="Al-Aqsa Computers — home">
            <img src="https://alaqsa.com.pk/wp-content/uploads/2021/06/logo-11-1.png" alt="Al-Aqsa Computers" className="h-10 w-auto" />
          </Link>

          {/* Search bar */}
          <div className="header-search-wrap">
            <input
              type="search"
              id="site-search"
              placeholder="What do you need?"
              value={search}
              onChange={(e) => onSearch(e.target.value)}
              className="header-search-input"
              aria-label="Search products"
            />
            <button className="header-search-btn" aria-label="Search">
              <Search className="h-4 w-4" />
              <span>SEARCH</span>
            </button>
          </div>

          {/* Right: AI toggle */}
          <div className="header-actions">
            <button
              id="ai-search-toggle"
              onClick={onAiToggle}
              aria-pressed={aiActive}
              className={`header-ai-btn ${aiActive ? "header-ai-btn--active" : ""}`}
            >
              <Sparkles className="h-4 w-4" />
              <span>AI Search</span>
            </button>
          </div>
        </div>
      </div>

      <nav className="header-nav-bar relative" role="navigation" aria-label="Main navigation">
        <div className="header-nav-inner flex">
          <Link to="/" className="header-nav-link flex items-center h-full px-4 text-sm font-medium hover:text-white/80 transition-colors">
            Home
          </Link>

          {/* Render Main Categories as Dropdowns */}
          {categoryTree.map((cat) => (
            <div key={cat.name} className="group inline-block h-full">
              <Link 
                to="/" 
                search={{ category: cat.name }}
                className="header-nav-link flex items-center gap-1 h-full px-4 text-sm font-medium hover:text-white/80 transition-colors cursor-pointer"
              >
                {cat.name}
                <ChevronDown className="h-3 w-3 opacity-70 transition-transform group-hover:rotate-180" />
              </Link>
              
              {/* Dropdown Menu */}
              <div className="absolute top-full left-auto hidden w-64 flex-col bg-white shadow-xl border border-border py-2 group-hover:flex z-50">
                {cat.subcategories.map((sub, idx) => (
                  <NavDropdownItem key={idx} item={sub} parentCategory={cat.name} />
                ))}
              </div>
            </div>
          ))}

          <a href="tel:+924237120011" className="header-nav-link flex items-center h-full px-4 text-sm font-medium hover:text-white/80 transition-colors ml-auto">
            Contact Us
          </a>
        </div>
      </nav>
    </header>
  );
}

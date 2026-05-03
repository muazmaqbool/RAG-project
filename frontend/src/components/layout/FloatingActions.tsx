import { useCompare } from "@/hooks/use-compare";
import { Link } from "@tanstack/react-router";

function WhatsAppIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-label="WhatsApp">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z" />
      <path d="M12 0C5.374 0 0 5.373 0 12c0 2.117.554 4.133 1.521 5.872L.057 23.98l6.304-1.654A11.935 11.935 0 0 0 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.816 9.816 0 0 1-5.001-1.371l-.359-.214-3.717.975.993-3.618-.235-.372A9.817 9.817 0 0 1 2.182 12C2.182 6.574 6.574 2.182 12 2.182S21.818 6.574 21.818 12 17.426 21.818 12 21.818z" />
    </svg>
  );
}

export function FloatingActions() {
  const { ids, clearCompare } = useCompare();

  return (
    <>
      {/* Compare Bar (Bottom Center) */}
      {ids.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-10 fade-in duration-300">
          <div className="bg-[#1a73e8] text-white px-6 py-3 rounded-full shadow-2xl flex items-center gap-4 font-medium">
            <span>{ids.length} item{ids.length !== 1 ? 's' : ''} added to compare</span>
            <div className="flex gap-3 border-l border-white/20 pl-4 items-center">
              <Link 
                to="/compare"
                className="bg-white text-[#1a73e8] px-3 py-1 rounded text-sm font-bold hover:bg-gray-100 transition-colors"
              >
                Compare Now
              </Link>
              <button 
                onClick={clearCompare}
                className="text-white/80 hover:text-white text-sm"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      )}

      {/* WhatsApp FAB (Bottom Right) */}
      <a
        href="https://wa.me/923367120011"
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-6 right-6 z-50 bg-[#25D366] text-white p-4 rounded-full shadow-lg hover:bg-[#20bd5a] transition-all hover:scale-110 flex items-center justify-center animate-pulse-slow"
        aria-label="Chat on WhatsApp"
      >
        <WhatsAppIcon />
      </a>
    </>
  );
}

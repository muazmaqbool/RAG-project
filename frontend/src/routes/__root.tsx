import { Outlet, Link, createRootRoute, HeadContent, Scripts } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Footer } from "@/components/layout/Footer";
import { FloatingActions } from "@/components/layout/FloatingActions";

import appCss from "../styles.css?url";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 1000 * 60 * 2, retry: 1 },
  },
});

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Al-Aqsa Computers — Best Electronics Prices in Lahore, Pakistan" },
      { name: "description", content: "Al-Aqsa Computers Lahore — Buy laptops, accessories, smart gadgets and electronics at the best prices in Pakistan." },
      { name: "author", content: "Al-Aqsa Computers" },
      { property: "og:site_name", content: "Al-Aqsa Computers" },
      { property: "og:type", content: "website" },
      { property: "og:locale", content: "en_PK" },
      { name: "twitter:card", content: "summary" },
      { name: "robots", content: "index, follow" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "canonical", href: "https://alaqsa.com.pk" },
    ],
    scripts: [
      {
        type: "application/ld+json",
        children: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "LocalBusiness",
          name: "Al-Aqsa Computers",
          url: "https://alaqsa.com.pk",
          description: "Electronics and laptop store in Lahore, Pakistan. Best prices on new and used laptops, accessories, and smart gadgets.",
          address: {
            "@type": "PostalAddress",
            addressLocality: "Lahore",
            addressRegion: "Punjab",
            addressCountry: "PK",
          },
          geo: {
            "@type": "GeoCoordinates",
            latitude: 31.5204,
            longitude: 74.3587,
          },
          areaServed: "Lahore, Pakistan",
          priceRange: "Rs. 500 - Rs. 500,000",
        }),
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
});

function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex min-h-screen flex-col w-full">
        <div className="flex-1 w-full">
          <Outlet />
        </div>
        <Footer />
        <FloatingActions />
      </div>
    </QueryClientProvider>
  );
}

'use client';

import Link from 'next/link';
import Image from 'next/image';

const G = '#0E7A4A';
const GD = '#166534';
const AU = '#BFA84F';

export default function GlobalNotFound() {
  return (
    <html lang="en">
      <head>
        <title>Page Not Found | Quran Competition</title>
        <meta name="theme-color" content={G} />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet" />
        <style>{`
          body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
            background-color: #f9fafb;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            position: relative;
          }
          
          /* Background geometric pattern using CSS gradients */
          .bg-pattern {
            position: absolute;
            inset: 0;
            background-color: ${G};
            background-image: 
              linear-gradient(30deg, ${GD} 12%, transparent 12.5%, transparent 87%, ${GD} 87.5%, ${GD}),
              linear-gradient(150deg, ${GD} 12%, transparent 12.5%, transparent 87%, ${GD} 87.5%, ${GD}),
              linear-gradient(30deg, ${GD} 12%, transparent 12.5%, transparent 87%, ${GD} 87.5%, ${GD}),
              linear-gradient(150deg, ${GD} 12%, transparent 12.5%, transparent 87%, ${GD} 87.5%, ${GD}),
              linear-gradient(60deg, ${GD}77 25%, transparent 25.5%, transparent 75%, ${GD}77 75%, ${GD}77), 
              linear-gradient(60deg, ${GD}77 25%, transparent 25.5%, transparent 75%, ${GD}77 75%, ${GD}77);
            background-size: 80px 140px;
            background-position: 0 0, 0 0, 40px 70px, 40px 70px, 0 0, 40px 70px;
            opacity: 0.15;
            z-index: -1;
          }

          .gradient-glow {
            position: absolute;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(191,168,79,0.15) 0%, rgba(14,122,74,0) 70%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: -1;
            border-radius: 50%;
          }

          .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            border-top: 3px solid ${AU};
            border-radius: 1rem;
            padding: 4rem 2.5rem;
            text-align: center;
            max-width: 32rem;
            width: 90%;
            box-shadow: 0 20px 40px rgba(0,0,0,0.08);
            position: relative;
            z-index: 10;
            animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
          }

          @keyframes slideUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
          }
          
          @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
          }

          .number {
            font-size: 8rem;
            font-weight: 800;
            line-height: 1;
            margin: 0;
            background: linear-gradient(135deg, ${G} 0%, ${AU} 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 10px 30px rgba(14,122,74,0.15);
            animation: float 6s ease-in-out infinite;
          }

          .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            background-color: ${G};
            color: #ffffff;
            font-weight: 700;
            font-size: 1rem;
            padding: 1rem 2rem;
            border-radius: 0.5rem;
            text-decoration: none;
            transition: all 0.2s;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 14px rgba(14,122,74,0.3);
            margin-top: 2rem;
          }

          .btn:hover {
            background-color: ${GD};
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(14,122,74,0.4);
          }
        `}</style>
      </head>
      <body>
        <div className="bg-pattern" />
        <div className="gradient-glow" />
        
        <div className="card">
          <div style={{ marginBottom: '2rem' }}>
            {/* Replace with actual domain / path if using local image without base */}
            <div style={{ display: 'inline-flex', padding: '1rem', backgroundColor: '#f0fdf4', borderRadius: '50%', border: \`2px solid \${AU}\`, marginBottom: '1rem' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke={G} strokeWidth={1.5} style={{ width: '3rem', height: '3rem' }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h1 className="number">404</h1>
          </div>
          
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#111827', margin: '0 0 0.5rem' }}>
            Page Not Found
          </h2>
          <p style={{ color: '#6B7280', fontSize: '0.9375rem', lineHeight: 1.6, margin: 0 }}>
            The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.
          </p>
          
          <Link href="/en" className="btn">
            <svg viewBox="0 0 20 20" fill="currentColor" style={{ width: '1.25rem', height: '1.25rem' }}>
              <path fillRule="evenodd" d="M9.707 14.707a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 1.414L7.414 9H15a1 1 0 110 2H7.414l2.293 2.293a1 1 0 010 1.414z" clipRule="evenodd" />
            </svg>
            Return to Homepage
          </Link>
        </div>
      </body>
    </html>
  );
}

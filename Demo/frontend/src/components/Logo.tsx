type LogoProps = {
  size?: number;
  variant?: "color" | "mono";
  className?: string;
};

// Traced directly from the source artwork (house + confirmed-match checkmark + ascending
// arrow) via contour extraction — same silhouette, just flat and edge-clean instead of glow.
const MARK_PATH =
  "M 163.6,122.6 L 142.9,122.3 L 142.0,113.9 L 138.2,103.9 L 133.1,97.9 L 130.9,97.1 L 123.2,97.3 L 114.5,101.6 L 111.6,102.1 L 107.3,105.6 L 104.9,106.4 L 95.1,114.3 L 94.0,114.3 L 86.1,107.2 L 77.8,101.6 L 75.4,101.1 L 69.3,97.6 L 65.9,97.9 L 64.8,97.1 L 61.9,97.1 L 59.5,98.9 L 58.4,98.9 L 54.3,103.9 L 49.5,115.3 L 49.0,121.9 L 48.3,122.6 L 28.7,122.6 L 27.8,122.2 L 27.5,120.1 L 26.7,106.0 L 24.3,99.9 L 19.4,94.7 L 17.0,93.4 L 14.6,94.2 L 3.6,83.4 L 2.5,81.5 L 21.2,63.1 L 86.9,2.5 L 87.9,2.8 L 104.9,18.2 L 108.9,20.3 L 115.0,26.4 L 117.9,27.5 L 127.8,33.9 L 132.5,35.5 L 140.2,33.6 L 144.6,30.3 L 145.2,27.1 L 147.3,23.1 L 144.8,19.0 L 173.7,12.9 L 197.1,9.2 L 197.5,11.2 L 194.0,28.7 L 187.1,56.0 L 186.5,56.4 L 182.7,53.8 L 174.2,54.8 L 170.3,57.2 L 165.9,63.2 L 164.8,69.9 L 165.6,71.4 L 166.1,79.2 L 165.6,80.2 L 166.1,86.9 L 165.6,90.3 L 166.1,91.1 L 165.3,115.3 L 164.8,122.2 L 163.6,122.6 Z " +
  "M 93.9,77.0 L 94.6,76.4 L 98.3,76.6 L 103.1,72.9 L 103.6,73.4 L 105.4,72.9 L 107.2,68.0 L 108.1,68.1 L 109.7,65.7 L 111.0,66.0 L 111.7,65.3 L 111.2,61.1 L 112.0,60.3 L 109.4,58.0 L 107.2,57.4 L 107.4,55.8 L 104.2,53.7 L 103.7,51.3 L 102.5,50.9 L 101.5,49.0 L 100.9,49.3 L 95.6,45.0 L 94.3,45.6 L 91.9,41.6 L 86.9,41.6 L 85.8,40.8 L 84.2,42.1 L 83.4,40.8 L 82.6,42.4 L 81.5,42.1 L 80.6,43.0 L 80.2,45.3 L 78.9,44.2 L 77.8,46.1 L 76.8,46.1 L 69.7,52.3 L 70.0,53.4 L 67.3,56.0 L 68.1,56.8 L 67.6,57.6 L 68.1,58.4 L 67.1,60.0 L 68.0,61.2 L 70.7,61.0 L 77.0,64.1 L 78.1,65.5 L 79.4,65.7 L 83.1,70.0 L 85.5,71.3 L 87.9,74.8 L 89.5,74.5 L 91.6,76.1 L 93.0,75.8 L 92.8,76.5 L 93.9,77.0 Z";

const VIEW_W = 200;
const VIEW_H = 125.0996015936255;
const ASPECT = VIEW_W / VIEW_H;

export function LogoMark({ size = 40, variant = "color", className = "" }: LogoProps) {
  return (
    <svg
      width={size * ASPECT}
      height={size}
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path d={MARK_PATH} fillRule="evenodd" fill={variant === "mono" ? "#FFFFFF" : "#FF6259"} />
    </svg>
  );
}

export function Logo({ size = 40, variant = "color", className = "" }: LogoProps) {
  const textColor = variant === "mono" ? "text-white" : "text-navy";
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} variant={variant} />
      <span className={`font-extrabold tracking-tight ${textColor}`} style={{ fontSize: size * 0.6 }}>
        machea
      </span>
    </div>
  );
}

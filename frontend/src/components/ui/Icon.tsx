interface IconProps {
  name: string;
  className?: string;
  size?: number;
  filled?: boolean;
  style?: React.CSSProperties;
}

export function Icon({ name, className = "", size = 20, filled = false, style }: IconProps) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={{
        fontSize: size,
        fontVariationSettings: `"FILL" ${filled ? 1 : 0}, "wght" 300, "GRAD" 0, "opsz" 24`,
        ...style,
      }}
    >
      {name}
    </span>
  );
}

export function CircuitBoard({ className }: { className?: string }) {
  return (
    <div
      className={`absolute inset-0 opacity-[0.03] pointer-events-none ${className}`}
      style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M10 10h10v10H10zm20 0h10v10H30zm20 0h10v10H50zm20 0h10v10H70zm20 0h10v10H90zM10 30h10v10H10zm20 0h10v10H30zm20 0h10v10H50zm20 0h10v10H70zm20 0h10v10H90z' fill='%23000' fill-rule='evenodd'/%3E%3C/svg%3E")`,
        backgroundSize: "24px 24px"
      }}
    />
  );
}

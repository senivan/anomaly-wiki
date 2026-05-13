interface ImgHolderProps {
  label: string;
  ratio?: string;
}

export function ImgHolder({ label, ratio = "4/3" }: ImgHolderProps) {
  return (
    <div className="imgholder" style={{ aspectRatio: ratio }}>
      <span>{label}</span>
    </div>
  );
}

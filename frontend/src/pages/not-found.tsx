import { Link } from 'wouter';
import { ArrowLeft, CircleHelp } from 'lucide-react';

export default function NotFound() {
  return (
    <main className="not-found-page"><div className="not-found-symbol"><CircleHelp size={27} /></div><div className="eyebrow">PÁGINA NO DISPONIBLE</div><h1>No encontramos esta dirección.</h1><p>Puede que el enlace haya cambiado o que no tengas acceso a esta sección.</p><Link href="/" className="secondary-button" data-testid="link-back-home"><ArrowLeft size={16} /> Volver al inicio</Link></main>
  );
}

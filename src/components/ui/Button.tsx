import type { ButtonHTMLAttributes } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger';

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'border border-navy-800 bg-navy-800 text-white hover:bg-navy-900',
  secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
  danger: 'border border-red-200 bg-red-50 text-red-600 hover:bg-red-100',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({
  variant = 'primary',
  className = '',
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex h-10 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy-700 disabled:pointer-events-none disabled:opacity-50 ${variantClasses[variant]} ${className}`}
      {...props}
    />
  );
}

import { CopyButton } from './ui'

export function JsonViewer({
  value,
  maxHeight = '18rem',
  filename = 'acl-config.json',
}: {
  value: unknown
  maxHeight?: string
  filename?: string
}) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-navy-900">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
        <span className="font-mono text-[11px] text-slate-300">{filename}</span>
        <span className="[&_button]:border-white/20 [&_button]:bg-transparent [&_button]:text-slate-200 [&_button:hover]:bg-white/10">
          <CopyButton text={text} />
        </span>
      </div>
      <pre
        className="mono-block overflow-auto px-3 py-3 text-slate-100"
        style={{ maxHeight }}
      >
        {text}
      </pre>
    </div>
  )
}

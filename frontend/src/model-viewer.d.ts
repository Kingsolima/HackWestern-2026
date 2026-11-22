import type { ModelViewerElement } from '@google/model-viewer'
import type { DetailedHTMLProps, HTMLAttributes } from 'react'

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'model-viewer': DetailedHTMLProps<HTMLAttributes<ModelViewerElement>, ModelViewerElement> & {
        src?: string
        'camera-controls'?: boolean
        'auto-rotate'?: boolean
        'camera-orbit'?: string
        'interaction-prompt'?: 'auto' | 'none'
      }
    }
  }
}

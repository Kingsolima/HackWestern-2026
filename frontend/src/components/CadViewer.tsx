import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { partRole, type PartRole } from '../modelParts'
import type { PartDetail } from '../partDetail'
import type { CadRobot, Level } from '../events'
import type { FreeArea } from '../stageArea'

interface Props {
  /** GLB url; null shows the empty grid. */
  src: string | null
  /** Which robot `src` draws: decides which parts are the deep line and the regenerated mount. */
  robot: CadRobot
  /** Highlight the deep line (a job is running) and the regenerated mount (the redesign is shown). */
  deep: boolean
  build: boolean
  /** What to say about a part (hover and pin); changes identity when the answer may change. */
  detail: (node: string, role: PartRole | null) => PartDetail
  /** Colour each part by its supply-risk level. */
  heat: boolean
  /** The part whose card is pinned, and the callback for a click on a part (null: empty space). */
  pinned: string | null
  onPick: (node: string | null) => void
  /** The part of the window no panel covers: the model is centred and fitted in it. */
  area: FreeArea
  onStatus?: (status: { parts: number; size_mm: [number, number, number] } | 'error') => void
}

const ORANGE = new THREE.Color('#f2a93b')
const EDGE = new THREE.Color('#cfcfcf')
const FILL = new THREE.Color('#151617')
const HEAT: Record<Level, THREE.Color> = {
  high: new THREE.Color('#ef5f52'),
  medium: new THREE.Color('#e4cf5a'),
  low: new THREE.Color('#6fcf8e'),
  unknown: new THREE.Color('#6a6a6a'),
}
const HOME_DIR = new THREE.Vector3(3.2, 2.1, 3.7).normalize()
const ease = (x: number) => 1 - Math.pow(1 - x, 3)

/** Camera distance at which the whole model fits the free area's narrower field of view. */
function fitDistance(w: World): number {
  const r = w.box.getBoundingSphere(new THREE.Sphere()).radius
  const v = THREE.MathUtils.degToRad(w.camera.fov) / 2
  const h = Math.atan(Math.tan(v) * w.camera.aspect * w.freeFrac)
  return (r / Math.sin(Math.min(v, h))) * 1.08
}

/** Move the camera along its current line of sight to `target`, at the fitting distance. */
function frame(w: World, target: THREE.Vector3) {
  const dir = w.camera.position.clone().sub(w.controls.target).normalize()
  w.tween = { s: performance.now(), t0: w.controls.target.clone(), t1: target, p0: w.camera.position.clone(), p1: target.clone().add(dir.multiplyScalar(fitDistance(w))) }
}

interface World {
  renderer: THREE.WebGLRenderer
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  controls: OrbitControls
  clip: THREE.Plane
  model: THREE.Object3D | null
  robot: CadRobot
  parts: Map<string, THREE.Object3D>
  box: THREE.Box3
  roles: Map<string, PartRole>
  hover: string | null
  pinned: string | null
  /** Risk level per part while the heat view is on; empty when it is off. */
  heat: Map<string, Level>
  shift: number
  shiftGoal: number
  /** Free area width / window width. */
  freeFrac: number
  grow: { t0: number; h: number } | null
  tween: { s: number; t0: THREE.Vector3; t1: THREE.Vector3; p0: THREE.Vector3; p1: THREE.Vector3 } | null
  applyView: () => void
}

function paint(w: World, name: string) {
  const part = w.parts.get(name)
  if (!part) return
  const role = w.roles.get(name)
  const level = w.heat.get(name)
  const pinned = w.pinned === name
  const lit = w.hover === name || pinned
  part.traverse((o) => {
    if (o instanceof THREE.Mesh) {
      const base = level
        ? HEAT[level].clone().multiplyScalar(0.3)
        : role === 'build'
          ? ORANGE.clone().multiplyScalar(0.32)
          : FILL.clone()
      ;(o.material as THREE.MeshStandardMaterial).color.copy(lit ? base.multiplyScalar(pinned ? 2.2 : 1.6) : base)
    }
    if (o instanceof THREE.LineSegments) {
      const m = o.material as THREE.LineBasicMaterial
      m.color.copy(pinned ? ORANGE : level ? HEAT[level] : role ? ORANGE : EDGE)
      m.opacity = role || lit || level ? 1 : 0.5
    }
  })
}

/** The full-screen CAD stage: dark solids with hairline edges, hover names a part, and the job's
 * parts turn orange. Camera and framing survive a model swap (before/after). */
export function CadViewer({ src, robot, deep, build, detail, heat, pinned, onPick, area, onStatus }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const tip = useRef<HTMLDivElement>(null)
  const world = useRef<World | null>(null)
  const detailRef = useRef(detail)
  detailRef.current = detail
  const pickRef = useRef(onPick)
  pickRef.current = onPick
  const heatRef = useRef(heat)
  heatRef.current = heat
  const robotRef = useRef(robot)
  robotRef.current = robot
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    const el = host.current
    if (!el) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      setOffline(true)
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.localClippingEnabled = true
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x07080a, 6, 14)
    const camera = new THREE.PerspectiveCamera(32, 1, 0.01, 100)
    camera.position.set(5.2, 3.4, 6.2)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.3
    controls.minDistance = 1.5
    controls.maxDistance = 12
    controls.target.set(0, 0.4, 0)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x0a0a0a, 1.1))
    const key = new THREE.DirectionalLight(0xffffff, 1.5)
    key.position.set(3, 5, 2)
    scene.add(key)
    scene.add(new THREE.GridHelper(12, 48, 0x2a2a2a, 0x161616))

    const w: World = {
      renderer, scene, camera, controls,
      clip: new THREE.Plane(new THREE.Vector3(0, -1, 0), 10),
      model: null, robot: 'wheeled', parts: new Map(), box: new THREE.Box3(), roles: new Map(),
      hover: null, pinned: null, heat: new Map(), shift: 0, shiftGoal: 0, freeFrac: 1, grow: null, tween: null,
      applyView: () => {
        const r = el.getBoundingClientRect()
        if (!r.width) return
        camera.aspect = r.width / r.height
        if (Math.abs(w.shift) > 0.5) camera.setViewOffset(r.width, r.height, -w.shift, 0, r.width, r.height)
        else camera.clearViewOffset()
        camera.updateProjectionMatrix()
      },
    }
    world.current = w

    const resize = () => {
      const r = el.getBoundingClientRect()
      if (!r.width) return
      renderer.setSize(r.width, r.height, false)
      w.applyView()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(el)

    const ray = new THREE.Raycaster()
    const ptr = new THREE.Vector2()
    const onMove = (e: PointerEvent) => {
      if (!w.model) return
      const r = renderer.domElement.getBoundingClientRect()
      ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      ray.setFromCamera(ptr, camera)
      const hit = ray.intersectObject(w.model, true).find((h) => h.object instanceof THREE.Mesh)
      let o: THREE.Object3D | null = hit?.object ?? null
      while (o && !w.parts.has(o.name)) o = o.parent
      const name = o?.name ?? null
      if (name !== w.hover) {
        const old = w.hover
        w.hover = name
        if (old) paint(w, old)
        if (name) paint(w, name)
      }
      const t = tip.current
      if (!t) return
      if (!name) return t.classList.remove('show')
      const d = detailRef.current(name, w.roles.get(name) ?? null)
      const set = (cls: string, text: string, tone = '') => {
        const el = t.querySelector<HTMLElement>(`.${cls}`)!
        el.textContent = text
        el.hidden = !text
        el.dataset.tone = tone
      }
      set('t', d.title)
      set('s', d.facts.join(' · '))
      const p = d.risk?.priority
      const score = p ? ` ${p.hi > p.lo ? `${p.lo}–${p.hi}` : p.lo}/9` : ''
      set('r', d.level ? `Risk ${d.level}${score}${d.worst ? ` · ${d.worst.name}: ${d.worst.value}` : ''}` : '', d.level ?? '')
      set('a', d.action ? `Action: ${d.action}` : '')
      set('o', d.role ?? '')
      set('h', w.pinned === name ? 'Pinned' : 'Click for details')
      t.style.left = `${e.clientX}px`
      t.style.top = `${e.clientY}px`
      t.classList.add('show')
    }
    const onLeave = () => {
      tip.current?.classList.remove('show')
      const old = w.hover
      w.hover = null
      if (old) paint(w, old)
    }
    // A click (not a drag to orbit) pins the part under the pointer, or unpins on empty space.
    let down: { x: number; y: number } | null = null
    const onDown = (e: PointerEvent) => {
      down = { x: e.clientX, y: e.clientY }
    }
    const onUp = (e: PointerEvent) => {
      if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 5) {
        onMove(e)
        pickRef.current(w.hover)
      }
      down = null
    }
    renderer.domElement.addEventListener('pointermove', onMove)
    renderer.domElement.addEventListener('pointerleave', onLeave)
    renderer.domElement.addEventListener('pointerdown', onDown)
    renderer.domElement.addEventListener('pointerup', onUp)

    let raf = 0
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (w.tween) {
        const k = ease(Math.min(1, (now - w.tween.s) / 1400))
        controls.target.lerpVectors(w.tween.t0, w.tween.t1, k)
        camera.position.lerpVectors(w.tween.p0, w.tween.p1, k)
        if (k >= 1) w.tween = null
      }
      if (w.grow) {
        const k = Math.min(1, (now - w.grow.t0) / 1800)
        w.clip.constant = -0.02 + (w.grow.h + 0.04) * ease(k)
        if (k >= 1) {
          w.grow = null
          w.clip.constant = 10
        }
      }
      if (Math.abs(w.shiftGoal - w.shift) > 0.5) {
        w.shift += (w.shiftGoal - w.shift) * 0.08
        w.applyView()
      }
      controls.update()
      renderer.render(scene, camera)
    }
    raf = requestAnimationFrame(frame)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      controls.dispose()
      renderer.dispose()
      renderer.domElement.remove()
      world.current = null
    }
  }, [])

  // Load or swap the model. The first model grows up from the floor and the camera moves in.
  useEffect(() => {
    const w = world.current
    if (!w) return
    let cancelled = false
    const clear = () => {
      if (w.model) w.scene.remove(w.model)
      w.model = null
      w.parts.clear()
    }
    if (!src) return clear()
    new GLTFLoader().load(
      src,
      (gltf) => {
        if (cancelled) return
        const first = w.model === null
        const before = w.robot
        clear()
        const model = gltf.scene
        w.robot = robotRef.current
        // The CAD worker nests a robot's parts under one root node, or writes them flat.
        const top = model.children
        for (const part of top.length === 1 && top[0].children.length ? top[0].children : top) w.parts.set(part.name, part)
        model.traverse((o) => {
          if (!(o instanceof THREE.Mesh)) return
          o.material = new THREE.MeshStandardMaterial({
            color: FILL, metalness: 0.3, roughness: 0.7, clippingPlanes: [w.clip],
            polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
          })
          o.add(new THREE.LineSegments(
            new THREE.EdgesGeometry(o.geometry, 28),
            new THREE.LineBasicMaterial({ color: EDGE, transparent: true, opacity: 0.5, clippingPlanes: [w.clip] }),
          ))
        })
        const box = new THREE.Box3().setFromObject(model)
        const size = box.getSize(new THREE.Vector3())
        const c = box.getCenter(new THREE.Vector3())
        const s = 2.1 / Math.max(size.x, size.y, size.z)
        model.scale.setScalar(s)
        model.position.set(-c.x * s, -box.min.y * s, -c.z * s)
        w.scene.add(model)
        w.model = model
        w.box.setFromObject(model)
        w.roles.clear()
        w.heat.clear()
        onStatus?.({ parts: w.parts.size, size_mm: [size.x, size.z, size.y].map(Math.round) as [number, number, number] })
        if (first) {
          w.grow = { t0: performance.now(), h: w.box.max.y }
          const center = w.box.getCenter(new THREE.Vector3())
          const home = center.clone().add(HOME_DIR.clone().multiplyScalar(fitDistance(w)))
          w.tween = { s: performance.now(), t0: w.controls.target.clone(), t1: center, p0: w.camera.position.clone(), p1: home }
        }
        else if (before !== w.robot) frame(w, w.box.getCenter(new THREE.Vector3())) // another robot
        setRoles(w, deep, build)
        setHeat(w, heatRef.current, detailRef.current)
      },
      undefined,
      () => !cancelled && onStatus?.('error'),
    )
    return () => {
      cancelled = true
    }
    // deep/build are applied by the effect below; a swap only re-applies them once loaded
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src])

  useEffect(() => {
    const w = world.current
    if (w) setRoles(w, deep, build)
  }, [deep, build])

  useEffect(() => {
    const w = world.current
    if (w) setHeat(w, heat, detail)
  }, [heat, detail])

  useEffect(() => {
    const w = world.current
    if (!w || w.pinned === pinned) return
    const old = w.pinned
    w.pinned = pinned
    if (old) paint(w, old)
    if (pinned) paint(w, pinned)
  }, [pinned])

  // The panels moved: slide the model into the new free area and fit it there.
  useEffect(() => {
    const w = world.current
    if (!w) return
    w.shiftGoal = area.shift
    const r = w.renderer.domElement.getBoundingClientRect()
    w.freeFrac = r.width ? Math.min(1, area.width / r.width) : 1
    if (w.model && !w.grow) frame(w, w.controls.target.clone())
  }, [area.shift, area.width])

  return (
    <div className="stage" ref={host}>
      {offline && <p className="stage-offline label">3D view unavailable: this browser has no WebGL</p>}
      {/* On body: the panels above the stage would otherwise cover the label. */}
      {createPortal(
        <div className="tip" ref={tip}>
          <div className="t" />
          <div className="s" />
          <div className="r" />
          <div className="a" />
          <div className="o" />
          <div className="h" />
        </div>,
        document.body,
      )}
    </div>
  )
}

/** Recolor parts for the job's state and, the first time the deep line lights up, turn toward it
 * while keeping the whole model in view. */
function setRoles(w: World, deep: boolean, build: boolean) {
  const hadDeep = [...w.roles.values()].includes('deep')
  w.roles.clear()
  for (const name of w.parts.keys()) {
    const role = partRole(w.robot, name, { deep, build })
    if (role) w.roles.set(name, role)
  }
  for (const name of w.parts.keys()) paint(w, name)
  w.controls.autoRotate = !deep
  const target = [...w.roles.entries()].find(([, r]) => r === 'deep')?.[0]
  if (!deep || hadDeep || !target || w.grow) return
  const c = w.box.getCenter(new THREE.Vector3())
  c.lerp(new THREE.Box3().setFromObject(w.parts.get(target)!).getCenter(new THREE.Vector3()), 0.25)
  frame(w, c)
}

/** Colour every part with a known risk level, or clear the colours. */
function setHeat(w: World, on: boolean, detail: Props['detail']) {
  w.heat.clear()
  if (on) {
    for (const name of w.parts.keys()) {
      const level = detail(name, null).level
      if (level) w.heat.set(name, level)
    }
  }
  for (const name of w.parts.keys()) paint(w, name)
}

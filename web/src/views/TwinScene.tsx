import { Component, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Text } from '@react-three/drei'
import * as THREE from 'three'
import interFontUrl from '@fontsource/inter/files/inter-latin-500-normal.woff?url'

const stages = [
  { id: 'sediment', label: 'SED', color: '#b7a780' }, { id: 'carbon', label: 'CARBON', color: '#566f6d' },
  { id: 'ro', label: 'RO', color: '#49d8cf' }, { id: 'uf', label: 'UF', color: '#678ec1' },
  { id: 'uv', label: 'UV', color: '#a58bd2' }, { id: 'alkaliser', label: 'MINERAL', color: '#cf967d' },
]

function WaterParticles({ flow }: { flow: number }) {
  const ref = useRef<THREE.InstancedMesh>(null)
  const object = useRef(new THREE.Object3D())
  const count = 120
  useFrame((state) => {
    if (!ref.current) return
    const phase = state.clock.elapsedTime * Math.min(1.8, 0.2 + flow / 40)
    for (let index = 0; index < count; index += 1) {
      const x = -3.1 + ((phase + index * 0.17) % 6.2)
      object.current.position.set(x, 0.05 + Math.sin(index * 8.2 + phase) * 0.035, 0.46)
      const scale = 0.012 + Math.min(0.016, flow / 1000)
      object.current.scale.setScalar(scale)
      object.current.updateMatrix()
      ref.current.setMatrixAt(index, object.current.matrix)
    }
    ref.current.instanceMatrix.needsUpdate = true
  })
  return <instancedMesh ref={ref} args={[undefined, undefined, count]}><sphereGeometry args={[1, 8, 8]} /><meshBasicMaterial color="#85fff0" transparent opacity={0.72} /></instancedMesh>
}

function Cartridge({ position, item, selected, preset, onSelect }: { position: number; item: typeof stages[number]; selected: boolean; preset: string; onSelect: (id: string) => void }) {
  const exploded = preset === 'exploded' ? (position - 2.5) * 0.16 : 0
  const opacity = preset === 'xray' ? 0.55 : 0.96
  return <group position={[-2.55 + position * 0.98 + exploded, 0.05, 0]} onClick={(event) => { event.stopPropagation(); onSelect(item.id) }}>
    <mesh position={[0, -0.04, 0]} castShadow>
      <cylinderGeometry args={[0.31, 0.31, 1.22, 32, 1, false]} />
      <meshPhysicalMaterial color={item.color} roughness={0.24} metalness={0.24} transparent opacity={opacity} clearcoat={0.65} />
    </mesh>
    <mesh position={[0, 0.59, 0]}><cylinderGeometry args={[0.33, 0.33, 0.12, 32]} /><meshStandardMaterial color={selected ? '#8effef' : '#8297a2'} metalness={0.5} /></mesh>
    <mesh position={[0, -0.68, 0]}><cylinderGeometry args={[0.33, 0.33, 0.12, 32]} /><meshStandardMaterial color="#354750" metalness={0.4} /></mesh>
    <mesh position={[0, 0.02, 0.25]}><boxGeometry args={[0.35, 0.09, 0.025]} /><meshStandardMaterial color={selected ? '#112a2d' : '#203039'} /></mesh>
    <Text font={interFontUrl} position={[0, -0.9, 0.35]} fontSize={0.13} color={selected ? '#a7fff2' : '#9eafb7'} anchorX="center" anchorY="middle" outlineWidth={0.002} outlineColor="#0b1118">{item.label}</Text>
    {selected && <mesh position={[0, 0, -0.38]}><torusGeometry args={[0.4, 0.018, 8, 40]} /><meshBasicMaterial color="#56dfcf" /></mesh>}
  </group>
}

function TwinModel({ flow, current, selected, preset, onSelect }: { flow: number; current: number; selected: string; preset: string; onSelect: (id: string) => void }) {
  const pumpRef = useRef<THREE.Group>(null)
  useFrame((state) => {
    if (pumpRef.current) pumpRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 18) * Math.min(0.025, current / 80)
  })
  return <>
    <color attach="background" args={['#0d151d']} />
    <ambientLight intensity={1.2} /><directionalLight position={[2, 4, 5]} intensity={2.1} color="#d9f5f2" />
    <pointLight position={[-3, 2, 3]} intensity={14} color="#41dccc" distance={9} />
    <pointLight position={[3, -1, -3]} intensity={8} color="#7f83d6" distance={7} />
    <mesh position={[0, -1.08, 0]} receiveShadow><boxGeometry args={[7.2, 0.08, 2.15]} /><meshStandardMaterial color="#14232c" roughness={0.55} metalness={0.25} /></mesh>
    <mesh position={[0, -0.32, -0.55]}><boxGeometry args={[6.65, 1.95, 0.08]} /><meshPhysicalMaterial color="#a4c1c7" transparent opacity={preset === 'xray' ? 0.09 : 0.14} roughness={0.18} metalness={0.3} /></mesh>
    <mesh position={[-3.02, -0.32, -0.55]}><boxGeometry args={[0.08, 1.95, 0.08]} /><meshStandardMaterial color="#526974" metalness={0.6} /></mesh>
    <mesh position={[3.02, -0.32, -0.55]}><boxGeometry args={[0.08, 1.95, 0.08]} /><meshStandardMaterial color="#526974" metalness={0.6} /></mesh>
    <mesh position={[0, 0.73, -0.55]}><boxGeometry args={[6.1, 0.08, 0.08]} /><meshStandardMaterial color="#526974" metalness={0.6} /></mesh>
    <mesh position={[0, -1.29, -0.55]}><boxGeometry args={[6.1, 0.08, 0.08]} /><meshStandardMaterial color="#526974" metalness={0.6} /></mesh>
    <mesh position={[-3.55, 0.05, 0.4]}><cylinderGeometry args={[0.18, 0.18, 0.7, 24]} /><meshStandardMaterial color="#678190" metalness={0.5} /></mesh>
    <mesh position={[-3.55, -0.43, 0.4]}><torusGeometry args={[0.19, 0.035, 10, 28]} /><meshStandardMaterial color="#49626f" metalness={0.7} /></mesh>
    {stages.map((item, index) => <Cartridge key={item.id} position={index} item={item} selected={selected === item.id} preset={preset} onSelect={onSelect} />)}
    <group ref={pumpRef} position={[0.42, 0.02, 0.45]}>
      <mesh rotation={[0, 0, Math.PI / 2]} castShadow><cylinderGeometry args={[0.32, 0.32, 0.57, 32]} /><meshStandardMaterial color="#274953" metalness={0.7} roughness={0.25} /></mesh>
      <mesh position={[0, 0, 0.29]}><torusGeometry args={[0.25, 0.045, 12, 32]} /><meshStandardMaterial color="#59dfd0" emissive="#174b49" /></mesh>
      <mesh position={[0, 0, 0.36]}><circleGeometry args={[0.09, 24]} /><meshBasicMaterial color="#a6fff3" /></mesh>
      <Text font={interFontUrl} position={[0, -0.58, 0.1]} fontSize={0.12} color="#a6bbc4" anchorX="center">BOOSTER PUMP</Text>
    </group>
    <group position={[3.13, -0.22, 0.3]}>
      <mesh><cylinderGeometry args={[0.46, 0.42, 1.38, 32]} /><meshPhysicalMaterial color="#3e6971" transparent opacity={0.45} roughness={0.16} metalness={0.14} /></mesh>
      <mesh position={[0, -0.27, 0]}><cylinderGeometry args={[0.4, 0.4, 0.78, 32]} /><meshStandardMaterial color="#257f80" transparent opacity={0.48} /></mesh>
      <mesh position={[0, 0.72, 0]}><cylinderGeometry args={[0.49, 0.49, 0.1, 32]} /><meshStandardMaterial color="#59747d" metalness={0.45} /></mesh>
      <Text font={interFontUrl} position={[0, -0.98, 0.1]} fontSize={0.13} color="#a8bbc2" anchorX="center">STORAGE TANK</Text>
    </group>
    <mesh position={[1.82, 0.02, 0.2]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.07, 0.07, 1.1, 12]} /><meshStandardMaterial color="#617c86" metalness={0.35} /></mesh>
    <mesh position={[-0.91, 0.16, 0.36]}><torusGeometry args={[0.17, 0.055, 10, 28]} /><meshStandardMaterial color="#c5a777" metalness={0.5} /></mesh>
    <WaterParticles flow={flow} />
    <Text font={interFontUrl} position={[-3.52, 0.58, 0.35]} fontSize={0.12} color="#a6bbc4" anchorX="center">FEED</Text>
    <Text font={interFontUrl} position={[1.5, 0.4, 0.48]} fontSize={0.11} color="#a6bbc4" anchorX="center">REJECT</Text>
    <OrbitControls enableDamping dampingFactor={0.08} minDistance={6.4} maxDistance={11} maxPolarAngle={Math.PI * 0.63} target={[0, -0.05, 0]} />
  </>
}

class SceneErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.setState({ failed: true }) }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

export function TwinScene({ flow, current, selected, preset, onSelect, fallback, force3d = false }: { flow: number; current: number; selected: string; preset: string; onSelect: (id: string) => void; fallback: ReactNode; force3d?: boolean }) {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [userForce3d, setUserForce3d] = useState(false)
  const [webgl, setWebgl] = useState(true)
  const [webglError, setWebglError] = useState(false)
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(query.matches)
    const change = () => setReduced(query.matches)
    query.addEventListener('change', change)
    try {
      const canvas = document.createElement('canvas')
      setWebgl(!!(canvas.getContext('webgl2') || canvas.getContext('webgl')))
    } catch { setWebgl(false) }
    return () => query.removeEventListener('change', change)
  }, [])
  const allow3d = force3d || userForce3d || !reduced
  if (!webgl || webglError) {
    return <div className="schematic-wrapper">
      <div className="three-fallback-notice">
        <span>WebGL is unavailable or graphics acceleration is disabled in your browser.</span>
      </div>
      {fallback}
    </div>
  }
  if (!allow3d) {
    return <div className="schematic-wrapper">
      <div className="three-fallback-notice">
        <span>Reduced motion active in system settings.</span>
        <button type="button" className="enable-3d-btn" onClick={() => setUserForce3d(true)}>Switch to 3D</button>
      </div>
      {fallback}
    </div>
  }
  return <div className="three-stage" aria-label="Interactive procedural 3D purifier twin" role="img">
    <SceneErrorBoundary fallback={fallback}><Canvas camera={{ position: [0, 2.1, 7.8], fov: 38 }} dpr={[1, 1.3]} gl={{ antialias: true, powerPreference: 'low-power' }} onCreated={({ gl }) => {
      gl.domElement.addEventListener('webglcontextlost', (event) => {
        event.preventDefault()
        setWebglError(true)
      }, { once: true })
    }}><TwinModel flow={flow} current={current} selected={selected} preset={preset} onSelect={onSelect} /></Canvas></SceneErrorBoundary>
    <div className="three-hint">Drag to orbit <span>·</span> Scroll to zoom</div>
  </div>
}

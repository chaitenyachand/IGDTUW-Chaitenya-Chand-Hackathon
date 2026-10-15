import { Line } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { GLOBE_COLORS, arcPairs, eventNodes, fibonacciSphere, greatCircle } from "./globe-data";

function Dots() {
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(fibonacciSphere(1800).flat(), 3));
    return g;
  }, []);
  return (
    <points geometry={geometry}>
      <pointsMaterial
        color={GLOBE_COLORS.ink}
        size={0.012}
        transparent
        opacity={0.25}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

function Node({ position }: { position: [number, number, number] }) {
  const ring = useRef<THREE.Mesh>(null);
  const mat = useRef<THREE.MeshBasicMaterial>(null);
  const state = useRef({ start: Math.random() * 4, period: 2.5 + Math.random() * 4 });
  const quat = useMemo(
    () =>
      new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 0, 1),
        new THREE.Vector3(...position).normalize(),
      ),
    [position],
  );

  useFrame(({ clock }) => {
    const t = (clock.elapsedTime - state.current.start) % state.current.period;
    const p = t < 0 ? 0 : Math.min(1, t / 1.4);
    if (ring.current && mat.current) {
      ring.current.scale.setScalar(0.4 + p * 2.6);
      mat.current.opacity = p >= 1 || t < 0 ? 0 : 0.7 * (1 - p);
    }
  });

  return (
    <group position={position} quaternion={quat}>
      <mesh>
        <circleGeometry args={[0.014, 16]} />
        <meshBasicMaterial color={GLOBE_COLORS.crimson} side={THREE.DoubleSide} />
      </mesh>
      <mesh ref={ring}>
        <ringGeometry args={[0.018, 0.024, 32]} />
        <meshBasicMaterial
          ref={mat}
          color={GLOBE_COLORS.crimson}
          transparent
          opacity={0}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

function Arc({ points, speed }: { points: [number, number, number][]; speed: number }) {
  // drei's Line forwards its ref to the Line2 object.
  const ref = useRef<{ material: { dashOffset: number } } | null>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.material.dashOffset -= delta * speed;
  });
  return (
    <Line
      ref={ref as never}
      points={points}
      color={GLOBE_COLORS.crimson}
      lineWidth={1}
      transparent
      opacity={0.55}
      dashed
      dashSize={0.08}
      gapSize={0.05}
    />
  );
}

function Globe() {
  const tilt = useRef<THREE.Group>(null);
  const spin = useRef<THREE.Group>(null);
  const nodes = useMemo(() => eventNodes(40), []);
  const arcs = useMemo(
    () => arcPairs(nodes.length, 12).map(([a, b]) => greatCircle(nodes[a]!, nodes[b]!)),
    [nodes],
  );

  useFrame(({ pointer }, delta) => {
    if (spin.current) spin.current.rotation.y += delta * 0.06;
    if (tilt.current) {
      const ease = 1 - Math.pow(0.04, delta);
      tilt.current.rotation.x += (-pointer.y * 0.25 + 0.25 - tilt.current.rotation.x) * ease;
      tilt.current.rotation.z += (-pointer.x * 0.12 - tilt.current.rotation.z) * ease;
      tilt.current.rotation.y += (pointer.x * 0.3 - tilt.current.rotation.y) * ease;
    }
  });

  return (
    <group ref={tilt}>
      <group ref={spin}>
        <Dots />
        {nodes.map((p, i) => (
          <Node key={i} position={p} />
        ))}
        {arcs.map((pts, i) => (
          <Arc key={i} points={pts} speed={0.15 + (i % 4) * 0.05} />
        ))}
      </group>
    </group>
  );
}

export default function GlobeCanvas() {
  return (
    <Canvas
      camera={{ position: [0, 0, 3], fov: 40 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true }}
    >
      <Globe />
    </Canvas>
  );
}

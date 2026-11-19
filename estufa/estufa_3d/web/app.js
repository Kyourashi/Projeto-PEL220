// =============================================================================
//  PEL220 - Estufa em 3D (Three.js): o "agora" da estufa, como um gêmeo digital.
//  A cada 5 s lê api/estado (o servidor busca no Orion o Device, a AgriGreenhouse e
//  a WeatherObserved) e atualiza a cena:
//    - DHT22, sensor de solo e os dois BH1750: ponto colorido pelas faixas da alface;
//    - o exaustor gira (fanState); as lâmpadas LED acendem (lampState);
//    - o gotejamento pinga e as manchas molhadas crescem com a umidade do solo (pumpState, soilMoisture);
//    - a névoa sai dos bicos no alto e evapora (mistState);
//    - a água sobe e desce na caixa (tankWaterVolume) e a vazão medida aparece na bomba;
//    - a luz da cena segue o BH1750 do teto (dia e noite da simulação);
//    - os limites de cor vêm da AgriGreenhouse no Orion, não deste arquivo.
// =============================================================================
import * as THREE from './vendor/three-0.187.0.min.js';

const { OrbitControls, CSS2DRenderer, CSS2DObject } = THREE;

// --- medidas e faixas -------------------------------------------------------------
const C = 10, L = 5, H_PAREDE = 2.4, H_CUMEEIRA = 3.4;     // m: 10 × 5 = 50 m², como no modelo
const FRIO = 18;                                           // °C: abaixo disso, frio para a alface
const VPD_FAIXA = [0.45, 1.25, 1.5];                       // kPa: úmido | faixa | atenção | estresse
const LUX_SOL = 50000;                                     // lx: meio-dia lá fora, na simulação (escurece a cena à noite)
const NOITE_LUX = 500;                                     // lx no teto: abaixo disso é noite
const RESERVA = [0.2, 0.4];                                // fração da caixa: vermelho | laranja | verde
const PADRAO = { fanOnTemperature: 24, fanOffTemperature: 22,
                 irrigationOnSoilMoisture: 30, irrigationOffSoilMoisture: 45,
                 lampOnOutdoorIlluminance: 15000, lampOffOutdoorIlluminance: 20000,
                 mistOnVaporPressureDeficit: 1.25, mistOffVaporPressureDeficit: 0.95 };
const COR = { verde: 0x73bf69, azul: 0x5794f2, laranja: 0xff9830, vermelho: 0xf2495c,
              amarelo: 0xfade2a, cinza: 0x8e8e8e, roxo: 0xb877d9, ouro: 0xf2cc0c, nevoa: 0x3fb8af };
const CSS = Object.fromEntries(Object.entries(COR).map(([k, v]) => [k, '#' + v.toString(16).padStart(6, '0')]));

const marcadores = [];                                     // pontos coloridos que pulsam
let semente = 20261119;                                    // sorteio fixo: a cena é sempre a mesma
const sorteio = () => (semente = (semente * 16807) % 2147483647) / 2147483647;

// --- cena, câmera, controles --------------------------------------------------------
const cena = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(43, innerWidth / innerHeight, 0.1, 200);
camera.position.set(-11.0, 6.3, 9.0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
document.getElementById('cena').appendChild(renderer.domElement);

const camadaRotulos = new CSS2DRenderer();
camadaRotulos.setSize(innerWidth, innerHeight);
camadaRotulos.domElement.className = 'rotulos';
document.body.appendChild(camadaRotulos.domElement);

const controles = new OrbitControls(camera, camadaRotulos.domElement);
controles.target.set(-1.2, 0.9, 0.2);
controles.enableDamping = true;
controles.maxPolarAngle = Math.PI * 0.48;
controles.minDistance = 4;
controles.maxDistance = 34;

// --- luz: sol, céu e noite ----------------------------------------------------------
const ceu = new THREE.HemisphereLight(0xdff0ff, 0x4d4030, 0.9);
const sol = new THREE.DirectionalLight(0xfff1d6, 2.4);
sol.position.set(-9, 15, 7);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -13, right: 13, top: 13, bottom: -13, near: 1, far: 50 });
sol.shadow.bias = -0.0004;
const noite = new THREE.AmbientLight(0x7d8fc4, 0.22);
cena.add(ceu, sol, noite);
const CEU_DIA = new THREE.Color(0xbfd9ee), CEU_NOITE = new THREE.Color(0x0e1a2b);
cena.background = CEU_DIA.clone();
cena.fog = new THREE.Fog(cena.background.clone(), 40, 95);

// --- materiais ------------------------------------------------------------------------
const mat = {
  grama: new THREE.MeshStandardMaterial({ color: 0x5f8a45, roughness: 1 }),
  brita: new THREE.MeshStandardMaterial({ color: 0xb9ab90, roughness: 1 }),
  metal: new THREE.MeshStandardMaterial({ color: 0xc9ced6, roughness: 0.45, metalness: 0.6 }),
  filme: new THREE.MeshPhysicalMaterial({ color: 0xeef8ff, roughness: 0.15, transparent: true, opacity: 0.13,
                                          side: THREE.DoubleSide, depthWrite: false }),
  madeira: new THREE.MeshStandardMaterial({ color: 0x8a6440, roughness: 0.9 }),
  terra: new THREE.MeshStandardMaterial({ color: 0x4a3427, roughness: 1 }),
  tubo: new THREE.MeshStandardMaterial({ color: 0x2b3036, roughness: 0.5, emissive: COR.azul, emissiveIntensity: 0 }),
  caixa: new THREE.MeshStandardMaterial({ color: 0x9aa3ad, roughness: 0.6 }),
  branco: new THREE.MeshStandardMaterial({ color: 0xf2f2f2, roughness: 0.5 }),
  placaAzul: new THREE.MeshStandardMaterial({ color: 0x2c5282, roughness: 0.5 }),
  placaPreta: new THREE.MeshStandardMaterial({ color: 0x1a202c, roughness: 0.5 }),
  casca: new THREE.MeshPhysicalMaterial({ color: 0x9cc3ee, roughness: 0.3, transparent: true, opacity: 0.22,
                                          side: THREE.DoubleSide, depthWrite: false }),
  tampa: new THREE.MeshStandardMaterial({ color: 0x1f4f8f, roughness: 0.5 }),
  agua: new THREE.MeshStandardMaterial({ color: 0x1f7fe0, roughness: 0.15, transparent: true, opacity: 0.88,
                                         emissive: 0x0f4fa0, emissiveIntensity: 0.3 }),
  pa: new THREE.MeshStandardMaterial({ color: 0x3a4048, roughness: 0.4, metalness: 0.5 }),
  molhado: new THREE.MeshStandardMaterial({ color: 0x24180f, roughness: 0.6, transparent: true, opacity: 0.6,
                                            depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }),
  gota: new THREE.MeshStandardMaterial({ color: 0x6ec3ff, roughness: 0.1, emissive: 0x3f9fff, emissiveIntensity: 0.7 }),
  led: new THREE.MeshStandardMaterial({ color: 0xfff3dd, emissive: 0xfff1dc, emissiveIntensity: 0 }),
  ledCorpo: new THREE.MeshStandardMaterial({ color: 0x2d3238, roughness: 0.5, metalness: 0.4 }),
  tuboNevoa: new THREE.MeshStandardMaterial({ color: 0x3a4048, roughness: 0.5, emissive: COR.nevoa, emissiveIntensity: 0 }),
};
const TERRA_SECA = new THREE.Color(0x7b5b42), TERRA_MOLHADA = new THREE.Color(0x352619);

// --- ajudantes ------------------------------------------------------------------------
const v = (x, y, z) => new THREE.Vector3(x, y, z);
const EIXO_Y = v(0, 1, 0);

function malha(geo, material, x, y, z, { sombra = true, recebe = false, pai = cena } = {}) {
  const m = new THREE.Mesh(geo, material);
  m.position.set(x, y, z);
  m.castShadow = sombra;
  m.receiveShadow = recebe;
  pai.add(m);
  return m;
}

function entre(geo, a, b, material) {                  // peça esticada de a até b (eixo Y da geometria)
  const d = new THREE.Vector3().subVectors(b, a);
  const m = new THREE.Mesh(geo, material);
  m.position.copy(a).addScaledVector(d, 0.5);
  m.quaternion.setFromUnitVectors(EIXO_Y, d.clone().normalize());
  m.castShadow = true;
  cena.add(m);
  return m;
}
const barra = (a, b, e = 0.06, material = mat.metal) =>
  entre(new THREE.BoxGeometry(e, a.distanceTo(b), e), a, b, material);
const cano = (a, b, r = 0.016, material = mat.tubo) =>
  entre(new THREE.CylinderGeometry(r, r, a.distanceTo(b), 10), a, b, material);

// --- chão --------------------------------------------------------------------------------
malha(new THREE.CircleGeometry(60, 64), mat.grama, 0, 0, 0, { sombra: false, recebe: true }).rotation.x = -Math.PI / 2;
malha(new THREE.BoxGeometry(C, 0.03, L), mat.brita, 0, 0.015, 0, { sombra: false, recebe: true });

// --- estrutura: pórticos a cada 2 m, calhas, cumeeira -----------------------------------
for (let x = -C / 2; x <= C / 2 + 1e-6; x += 2) {
  for (const s of [-1, 1]) {
    barra(v(x, 0, s * L / 2), v(x, H_PAREDE, s * L / 2));
    barra(v(x, H_PAREDE, s * L / 2), v(x, H_CUMEEIRA, 0), 0.055);
  }
}
for (const [y, z] of [[H_PAREDE, -L / 2], [H_PAREDE, L / 2], [H_CUMEEIRA, 0], [0.06, -L / 2], [0.06, L / 2]]) {
  barra(v(-C / 2, y, z), v(C / 2, y, z), 0.05);
}

// --- filme plástico: laterais, telhado e oitões (porta na frente, exaustor no fundo) -----
const DY = H_CUMEEIRA - H_PAREDE;
for (const s of [-1, 1]) {
  malha(new THREE.PlaneGeometry(C, H_PAREDE), mat.filme, 0, H_PAREDE / 2, s * L / 2, { sombra: false });
  const telhado = malha(new THREE.PlaneGeometry(C, Math.hypot(L / 2, DY)), mat.filme,
                        0, H_PAREDE + DY / 2, s * L / 4, { sombra: false });
  telhado.rotation.x = Math.atan2(-s * L / 2, DY);
}
const PORTA = { largura: 1.2, altura: 2.1 };
const EXAUSTOR = { y: 1.55, lado: 1.0 };
function oitao(x, furo) {
  const forma = new THREE.Shape();
  forma.moveTo(-L / 2, 0); forma.lineTo(L / 2, 0); forma.lineTo(L / 2, H_PAREDE);
  forma.lineTo(0, H_CUMEEIRA); forma.lineTo(-L / 2, H_PAREDE); forma.closePath();
  const [z0, z1, y0, y1] = furo;
  const vazio = new THREE.Path();
  vazio.moveTo(z0, y0); vazio.lineTo(z1, y0); vazio.lineTo(z1, y1); vazio.lineTo(z0, y1); vazio.closePath();
  forma.holes.push(vazio);
  const m = new THREE.Mesh(new THREE.ShapeGeometry(forma), mat.filme);
  m.rotation.y = Math.PI / 2;
  m.position.x = x;
  cena.add(m);
}
oitao(-C / 2, [-PORTA.largura / 2, PORTA.largura / 2, 0, PORTA.altura]);
oitao(C / 2, [-EXAUSTOR.lado / 2, EXAUSTOR.lado / 2, EXAUSTOR.y - EXAUSTOR.lado / 2, EXAUSTOR.y + EXAUSTOR.lado / 2]);
for (const z of [-PORTA.largura / 2, PORTA.largura / 2]) barra(v(-C / 2, 0, z), v(-C / 2, PORTA.altura, z), 0.07);
barra(v(-C / 2, PORTA.altura, -PORTA.largura / 2), v(-C / 2, PORTA.altura, PORTA.largura / 2), 0.07);

// --- canteiros e alfaces -------------------------------------------------------------
const CAMAS = [-1.6, 0, 1.6], COMP = 8.4, LARG = 1.0, ALT = 0.25, CX = 0.2;
for (const z of CAMAS) {
  malha(new THREE.BoxGeometry(COMP, ALT, LARG), mat.madeira, CX, ALT / 2, z, { recebe: true });
  malha(new THREE.BoxGeometry(COMP - 0.08, 0.02, LARG - 0.08), mat.terra, CX, ALT + 0.005, z, { sombra: false, recebe: true });
}
const POR_FILEIRA = 27;
const geoAlface = new THREE.SphereGeometry(0.15, 12, 8);
geoAlface.scale(1, 0.55, 1);
const alfaces = new THREE.InstancedMesh(geoAlface, new THREE.MeshStandardMaterial({ roughness: 0.8 }),
                                        CAMAS.length * 2 * POR_FILEIRA);
{
  const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), e = new THREE.Vector3();
  const cor = new THREE.Color();
  let i = 0;
  for (const z of CAMAS) for (const dz of [-0.24, 0.24]) for (let k = 0; k < POR_FILEIRA; k++) {
    const escala = 0.8 + sorteio() * 0.35;
    p.set(CX - COMP / 2 + 0.3 + k * 0.3, ALT + 0.05, z + dz);
    q.setFromAxisAngle(EIXO_Y, sorteio() * Math.PI);
    alfaces.setMatrixAt(i, m4.compose(p, q, e.set(escala, escala, escala)));
    alfaces.setColorAt(i, cor.setHSL(0.26 + sorteio() * 0.06, 0.55 + sorteio() * 0.2, 0.34 + sorteio() * 0.12));
    i++;
  }
}
alfaces.castShadow = true;
alfaces.receiveShadow = true;
cena.add(alfaces);

// --- irrigação: caixa d'água e bomba do lado de fora, cabeçal e gotejadores -----------
const XC = CX - COMP / 2 + 0.15;                     // cabeçal, logo depois da porta
for (const z of CAMAS) for (const dz of [-0.12, 0.12]) {
  cano(v(XC, ALT + 0.03, z + dz), v(CX + COMP / 2 - 0.1, ALT + 0.03, z + dz), 0.012);
  cano(v(XC, 0.12, z + dz), v(XC, ALT + 0.03, z + dz), 0.012);
}
cano(v(XC, 0.12, CAMAS[0] - 0.12), v(XC, 0.12, CAMAS[2] + 0.12), 0.02);
cano(v(-C / 2 - 1.0, 0.12, CAMAS[0] - 0.12), v(XC, 0.12, CAMAS[0] - 0.12), 0.02);
// gotejadores a cada 0,6 m: mancha molhada que cresce com a umidade do solo e gota que pinga com a bomba
const GOTEJADORES = [];
for (const z of CAMAS) for (const dz of [-0.12, 0.12]) {
  for (let x = XC + 0.45; x < CX + COMP / 2 - 0.2; x += 0.6) GOTEJADORES.push(v(x, ALT + 0.03, z + dz));
}
const geoMancha = new THREE.CircleGeometry(1, 20);
geoMancha.rotateX(-Math.PI / 2);
const manchas = new THREE.InstancedMesh(geoMancha, mat.molhado, GOTEJADORES.length);
const gotas = new THREE.InstancedMesh(new THREE.SphereGeometry(0.022, 10, 8), mat.gota, GOTEJADORES.length);
manchas.renderOrder = 1;
cena.add(manchas, gotas);
const _m4 = new THREE.Matrix4(), _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _e = new THREE.Vector3();
function desenharGotejadores(molhado, bomba, t) {
  const m4 = _m4, q = _q, p = _p, e = _e;
  GOTEJADORES.forEach((g, i) => {
    const r = 0.05 + 0.17 * molhado + (bomba ? 0.02 * Math.sin(t * 3 + i) : 0);
    manchas.setMatrixAt(i, m4.compose(p.set(g.x, ALT + 0.018, g.z), q, e.set(r, 1, r)));
    const fase = (t * 1.6 + i * 0.37) % 1;              // cada gota cai do tubo até o solo e recomeça
    const s = bomba ? 1 - 0.4 * fase : 0.001;
    gotas.setMatrixAt(i, m4.compose(p.set(g.x, ALT + 0.03 - 0.025 * fase, g.z), q, e.set(s, s * 1.3, s)));
  });
  manchas.instanceMatrix.needsUpdate = true;
  gotas.instanceMatrix.needsUpdate = true;
}

const CAIXA = { x: -C / 2 - 1.85, z: -1.7, r: 0.46, h: 0.95, hAgua: 0.75 };  // D 0,92 m: 500 L até 0,75 m de altura
malha(new THREE.CylinderGeometry(CAIXA.r, CAIXA.r, CAIXA.h, 32, 1, true), mat.casca, CAIXA.x, CAIXA.h / 2, CAIXA.z, { sombra: false });
malha(new THREE.CylinderGeometry(CAIXA.r + 0.02, CAIXA.r + 0.02, 0.04, 32), mat.tampa, CAIXA.x, CAIXA.h + 0.02, CAIXA.z);
malha(new THREE.CylinderGeometry(CAIXA.r, CAIXA.r, 0.02, 32), mat.tampa, CAIXA.x, 0.01, CAIXA.z);
const agua = malha(new THREE.CylinderGeometry(CAIXA.r - 0.015, CAIXA.r - 0.015, 1, 32), mat.agua, CAIXA.x, 0.5, CAIXA.z, { sombra: false });
malha(new THREE.BoxGeometry(0.11, 0.04, 0.06), mat.placaAzul, CAIXA.x + 0.12, CAIXA.h + 0.06, CAIXA.z);   // placa do ultrassom
malha(new THREE.CylinderGeometry(0.03, 0.03, 0.07, 16), mat.placaPreta, CAIXA.x, CAIXA.h + 0.02, CAIXA.z);  // sonda, olhando para a água
const mCaixa = marcador(CAIXA.x, CAIXA.h + 0.26, CAIXA.z);
const medidor = malha(new THREE.CylinderGeometry(0.04, 0.04, 0.14, 16), mat.placaPreta, -C / 2 - 0.65, 0.12, CAMAS[0] - 0.12);
medidor.rotation.z = Math.PI / 2;                     // medidor de vazão no cano, depois da bomba
malha(new THREE.CylinderGeometry(0.022, 0.022, 0.05, 12), mat.branco, -C / 2 - 0.65, 0.18, CAMAS[0] - 0.12);
malha(new THREE.BoxGeometry(0.36, 0.24, 0.26), mat.caixa, -C / 2 - 1.15, 0.13, CAMAS[0] - 0.12);
const motor = malha(new THREE.CylinderGeometry(0.1, 0.1, 0.3, 18), mat.placaAzul, -C / 2 - 1.45, 0.13, CAMAS[0] - 0.12);
motor.rotation.z = Math.PI / 2;
cano(v(CAIXA.x + CAIXA.r, 0.12, CAIXA.z), v(-C / 2 - 1.33, 0.12, CAMAS[0] - 0.12), 0.02);
const luzBomba = malha(new THREE.SphereGeometry(0.05, 16, 12),
                       new THREE.MeshStandardMaterial({ color: COR.azul, emissive: COR.azul, emissiveIntensity: 0.05 }),
                       -C / 2 - 1.15, 0.3, CAMAS[0] - 0.12, { sombra: false });

// --- exaustor no oitão do fundo -------------------------------------------------------
const XE = C / 2;
{
  const a = EXAUSTOR.lado / 2, y = EXAUSTOR.y;
  for (const [p, q] of [[v(XE, y - a, -a), v(XE, y - a, a)], [v(XE, y + a, -a), v(XE, y + a, a)],
                        [v(XE, y - a, -a), v(XE, y + a, -a)], [v(XE, y - a, a), v(XE, y + a, a)]]) {
    barra(p, q, 0.09, mat.caixa);
  }
  const grade = malha(new THREE.TorusGeometry(0.43, 0.012, 8, 48), mat.metal, XE + 0.04, y, 0, { sombra: false });
  grade.rotation.y = Math.PI / 2;
}
const rotor = new THREE.Group();
rotor.position.set(XE - 0.02, EXAUSTOR.y, 0);
cena.add(rotor);
{
  const cubo = malha(new THREE.CylinderGeometry(0.07, 0.07, 0.12, 16), mat.pa, 0, 0, 0, { pai: rotor });
  cubo.rotation.z = Math.PI / 2;
  for (let k = 0; k < 3; k++) {
    const braco = new THREE.Group();
    braco.rotation.x = k * 2 * Math.PI / 3;
    const pa = malha(new THREE.BoxGeometry(0.02, 0.36, 0.15), mat.pa, 0, 0.23, 0, { pai: braco });
    pa.rotation.y = 0.45;                            // passo da pá
    rotor.add(braco);
  }
}

// --- o nó ESP32, na parede da frente ----------------------------------------------------
malha(new THREE.BoxGeometry(0.07, 0.26, 0.2), mat.caixa, -C / 2 + 0.06, 1.3, 1.55);
const led = malha(new THREE.SphereGeometry(0.022, 12, 8),
                  new THREE.MeshStandardMaterial({ color: COR.verde, emissive: COR.verde, emissiveIntensity: 0.1 }),
                  -C / 2 + 0.11, 1.4, 1.55, { sombra: false });

// --- lâmpadas LED sobre os canteiros (penduradas nos pórticos) -------------------------
const Y_LED = 2.1;
const alturaTelhado = (z) => H_PAREDE + (1 - Math.abs(z) / (L / 2)) * (H_CUMEEIRA - H_PAREDE);
const luzesLed = [];
for (const z of CAMAS) {
  malha(new THREE.BoxGeometry(COMP - 0.6, 0.05, 0.12), mat.ledCorpo, CX, Y_LED, z);
  malha(new THREE.BoxGeometry(COMP - 0.7, 0.012, 0.08), mat.led, CX, Y_LED - 0.031, z, { sombra: false });
  for (const x of [-2, 0, 2]) cano(v(x + CX, Y_LED, z), v(x + CX, alturaTelhado(z), z), 0.004, mat.metal);
  for (const x of [-2.1, 2.5]) {
    const p = new THREE.PointLight(0xfff1dc, 0, 5.5, 1.6);
    p.position.set(x, Y_LED - 0.25, z);
    cena.add(p);
    luzesLed.push(p);
  }
}

// --- nebulização: bomba de pressão, duas linhas no alto e 10 bicos ---------------------
const Y_NEVOA = 2.3, Z_NEVOA = [-0.8, 0.8], X_BICOS = [-4, -2, 0, 2, 4];
malha(new THREE.BoxGeometry(0.22, 0.16, 0.18), mat.caixa, -C / 2 - 1.15, 0.09, -0.75);     // bomba de diafragma
cano(v(CAIXA.x + CAIXA.r - 0.05, 0.08, CAIXA.z + 0.2), v(-C / 2 - 1.26, 0.08, -0.75), 0.012, mat.tuboNevoa);
cano(v(-C / 2 - 1.04, 0.08, -0.75), v(-C / 2 + 0.25, 0.08, -0.75), 0.012, mat.tuboNevoa);
cano(v(-C / 2 + 0.25, 0.08, -0.75), v(-C / 2 + 0.25, Y_NEVOA, -0.75), 0.012, mat.tuboNevoa);
cano(v(-C / 2 + 0.25, Y_NEVOA, Z_NEVOA[0]), v(-C / 2 + 0.25, Y_NEVOA, Z_NEVOA[1]), 0.012, mat.tuboNevoa);
const BICOS = [];
for (const z of Z_NEVOA) {
  cano(v(-C / 2 + 0.25, Y_NEVOA, z), v(X_BICOS[X_BICOS.length - 1] + 0.3, Y_NEVOA, z), 0.012, mat.tuboNevoa);
  for (const x of X_BICOS) {
    malha(new THREE.CylinderGeometry(0.018, 0.01, 0.06, 10), mat.metal, x, Y_NEVOA - 0.04, z, { sombra: false });
    BICOS.push(v(x, Y_NEVOA - 0.08, z));
  }
}

// névoa: partículas que saem dos bicos, se espalham, descem devagar e evaporam (somem)
function escalaPontos() {                             // pixels por metro, a 1 m da câmera
  return renderer.getPixelRatio() * innerHeight / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
}
function texturaRedonda() {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d'), grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.45, 'rgba(255,255,255,0.45)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}
const POR_BICO = 80, N_NEVOA = BICOS.length * POR_BICO;
const posNevoa = new Float32Array(N_NEVOA * 3), alfaNevoa = new Float32Array(N_NEVOA), tamNevoa = new Float32Array(N_NEVOA);
const velNevoa = new Float32Array(N_NEVOA * 3), idadeNevoa = new Float32Array(N_NEVOA).fill(99);
const vidaNevoa = new Float32Array(N_NEVOA);
const geoNevoa = new THREE.BufferGeometry();
geoNevoa.setAttribute('position', new THREE.BufferAttribute(posNevoa, 3));
geoNevoa.setAttribute('alfa', new THREE.BufferAttribute(alfaNevoa, 1));
geoNevoa.setAttribute('tamanho', new THREE.BufferAttribute(tamNevoa, 1));
const nevoa = new THREE.Points(geoNevoa, new THREE.ShaderMaterial({
  uniforms: { mapa: { value: texturaRedonda() }, cor: { value: new THREE.Color(0xf4f9ff) },
              escala: { value: escalaPontos() } },
  vertexShader: `attribute float alfa; attribute float tamanho; uniform float escala; varying float vAlfa;
    void main() { vAlfa = alfa; vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = tamanho * escala / -mv.z; gl_Position = projectionMatrix * mv; }`,
  fragmentShader: `uniform sampler2D mapa; uniform vec3 cor; varying float vAlfa;
    void main() { vec4 t = texture2D(mapa, gl_PointCoord); gl_FragColor = vec4(cor, t.a * vAlfa); }`,
  transparent: true, depthWrite: false,
}));
nevoa.frustumCulled = false;
cena.add(nevoa);
function animarNevoa(ligada, dt) {
  for (let i = 0; i < N_NEVOA; i++) {
    if (idadeNevoa[i] >= vidaNevoa[i]) {
      if (!ligada || Math.random() > dt * 2.2) { alfaNevoa[i] = 0; continue; }   // nasce aos poucos
      const b = BICOS[Math.floor(i / POR_BICO)], ang = Math.random() * Math.PI * 2, abre = 0.25 + Math.random() * 0.35;
      posNevoa.set([b.x, b.y, b.z], i * 3);
      velNevoa.set([Math.cos(ang) * abre, -0.12 - Math.random() * 0.25, Math.sin(ang) * abre], i * 3);
      idadeNevoa[i] = 0;
      vidaNevoa[i] = 1.8 + Math.random() * 1.6;
    }
    idadeNevoa[i] += dt;
    const k = i * 3, f = idadeNevoa[i] / vidaNevoa[i];
    velNevoa[k] *= 1 - dt * 0.9; velNevoa[k + 2] *= 1 - dt * 0.9; velNevoa[k + 1] -= dt * 0.03;
    posNevoa[k] += velNevoa[k] * dt; posNevoa[k + 1] += velNevoa[k + 1] * dt; posNevoa[k + 2] += velNevoa[k + 2] * dt;
    alfaNevoa[i] = 0.8 * Math.min(1, f * 5) * (1 - f);     // aparece rápido e evapora no fim da vida
    tamNevoa[i] = 0.15 + 0.8 * f;                           // a gotícula vira nuvem
  }
  geoNevoa.attributes.position.needsUpdate = true;
  geoNevoa.attributes.alfa.needsUpdate = true;
  geoNevoa.attributes.tamanho.needsUpdate = true;
}

// --- sensores: haste, placa e um ponto colorido pela faixa ------------------------------
function marcador(x, y, z) {
  const m = malha(new THREE.SphereGeometry(0.08, 24, 16),
                  new THREE.MeshStandardMaterial({ color: COR.cinza, emissive: COR.cinza, emissiveIntensity: 0.7, roughness: 0.3 }),
                  x, y, z, { sombra: false });
  marcadores.push(m);
  return m;
}
function pintar(m, nome) {
  m.material.color.setHex(COR[nome]);
  m.material.emissive.setHex(COR[nome]);
}

const DHT = v(1.4, 0, -0.8);                         // corredor entre os canteiros 1 e 2
cano(v(DHT.x, 0, DHT.z), v(DHT.x, 1.45, DHT.z), 0.018, mat.metal);
malha(new THREE.BoxGeometry(0.06, 0.1, 0.045), mat.branco, DHT.x, 1.5, DHT.z);
const mDht = marcador(DHT.x, 1.7, DHT.z);

const SOLO = v(2.6, 0, 1.6);                         // no canteiro da frente
malha(new THREE.BoxGeometry(0.03, 0.16, 0.012), mat.placaPreta, SOLO.x, ALT + 0.06, SOLO.z);
const mSolo = marcador(SOLO.x, ALT + 0.3, SOLO.z);

const BH = v(-2.4, 0, -0.8);                         // corredor entre os canteiros 1 e 2
cano(v(BH.x, 0, BH.z), v(BH.x, 1.15, BH.z), 0.018, mat.metal);
malha(new THREE.BoxGeometry(0.06, 0.01, 0.06), mat.placaAzul, BH.x, 1.16, BH.z);
const mBh = marcador(BH.x, 1.36, BH.z);

const BH_TETO = v(1.0, H_CUMEEIRA, 0);               // no teto, do lado de fora do filme, olhando para o céu
cano(v(BH_TETO.x, H_CUMEEIRA, 0), v(BH_TETO.x, H_CUMEEIRA + 0.12, 0), 0.012, mat.metal);
malha(new THREE.BoxGeometry(0.06, 0.01, 0.06), mat.placaAzul, BH_TETO.x, H_CUMEEIRA + 0.125, 0);
const mBhTeto = marcador(BH_TETO.x, H_CUMEEIRA + 0.3, 0);
pintar(mBhTeto, 'roxo');

const FORA = v(3.6, 0, L / 2 + 1.9);                 // estação do clima, do lado de fora
cano(v(FORA.x, 0, FORA.z), v(FORA.x, 1.8, FORA.z), 0.025, mat.metal);
for (let k = 0; k < 4; k++) malha(new THREE.CylinderGeometry(0.12, 0.12, 0.035, 20), mat.branco, FORA.x, 1.82 + k * 0.06, FORA.z);
const mFora = marcador(FORA.x, 2.2, FORA.z);
pintar(mFora, 'roxo');

// --- rótulos (HTML presos a pontos da cena) -------------------------------------------
function rotulo(x, y, z) {
  const div = document.createElement('div');
  div.className = 'rotulo';
  const obj = new CSS2DObject(div);
  obj.position.set(x, y, z);
  obj.center.set(0.5, 1);                            // a ponta de baixo do rótulo fica no ponto
  cena.add(obj);
  return div;
}
const rot = {
  dht: rotulo(DHT.x, 1.82, DHT.z),
  solo: rotulo(SOLO.x, ALT + 0.42, SOLO.z),
  bh: rotulo(BH.x, 1.48, BH.z),
  bhTeto: rotulo(BH_TETO.x, H_CUMEEIRA + 0.42, 0),
  lampadas: rotulo(-4.7, Y_LED - 0.1, CAMAS[0]),
  nevoa: rotulo(-C / 2 - 1.15, 0.3, -0.75),         // na bomba da névoa, como a do gotejamento
  vent: rotulo(XE, EXAUSTOR.y + 0.62, 0),
  bomba: rotulo(-C / 2 - 0.65, 0.3, CAMAS[0] - 0.12),
  caixa: rotulo(CAIXA.x, CAIXA.h + 0.8, CAIXA.z),
  esp: rotulo(-C / 2 + 0.06, 1.5, 1.55),
  fora: rotulo(FORA.x, 2.32, FORA.z),
};

// rótulos que se encostam na tela sobem até ficar livres (refeito 5 vezes por segundo)
const todosRotulos = Object.values(rot);
let proximaArrumacao = 0;
function arrumarRotulos(agora) {
  if (agora < proximaArrumacao) return;
  proximaArrumacao = agora + 0.2;
  const caixas = todosRotulos.map((d) => {
    const r = d.getBoundingClientRect(), sobe = Number(d.dataset.sobe || 0);
    return { d, x0: r.left, x1: r.right, y0: r.top + sobe, y1: r.bottom + sobe, sobe: 0, ok: r.width > 0 };
  }).filter((c) => c.ok).sort((a, b) => b.y1 - a.y1);   // de baixo para cima
  const postas = [];
  for (const c of caixas) {
    for (let volta = 0; volta < 8; volta++) {
      const bate = postas.find((o) => c.x0 < o.x1 + 4 && c.x1 > o.x0 - 4 &&
                                      c.y0 - c.sobe < o.y1 - o.sobe + 4 && c.y1 - c.sobe > o.y0 - o.sobe - 4);
      if (!bate) break;
      c.sobe = c.y1 - (bate.y0 - bate.sobe) + 4;
    }
    postas.push(c);
    c.d.dataset.sobe = c.sobe;
    c.d.style.marginTop = `${-c.sobe}px`;
  }
}

// --- dados: api/estado a cada 5 s -------------------------------------------------------
const num = (x, casas = 1) => x == null ? '—' :
  Number(x).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
const bola = (nome) => `<i style="background:${CSS[nome]}"></i>`;
const escapar = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function corTemperatura(t, e) {
  if (t == null) return 'cinza';
  if (t < FRIO) return 'azul';
  return t >= e.fanOnTemperature ? 'vermelho' : 'verde';
}
function corSolo(m, e) {
  if (m == null) return 'cinza';
  if (m < e.irrigationOnSoilMoisture) return 'vermelho';
  return m >= e.irrigationOffSoilMoisture ? 'azul' : 'verde';
}
function corVpd(x) {
  if (x == null) return 'cinza';
  if (x < VPD_FAIXA[0]) return 'azul';
  if (x < VPD_FAIXA[1]) return 'verde';
  return x < VPD_FAIXA[2] ? 'laranja' : 'vermelho';
}
function preencher(div, cor, titulo, valor, detalhe = '') {
  div.style.borderTopColor = CSS[cor];
  div.innerHTML = `<b>${titulo}</b><div class="v">${bola(cor)}${valor}</div>` +
                  (detalhe ? `<div class="s">${detalhe}</div>` : '');
}

let alvoLuz = 1, luzAtual = 1, alvoGiro = 0, giro = 0, bombaLigada = false, alvoAgua = 0.95, nivel = 0.95;
let alvoMolhado = 0.5, molhado = 0.5, lampadasLigadas = false, brilhoLed = 0, nevoaLigada = false;
let ultimaResposta = 0, ultimaMedida = null, falha = null, semNo = false, primeira = true;

function aplicar(estado) {
  const no = estado.no || {}, clima = estado.clima || {};
  const e = Object.assign({}, PADRAO, estado.estufa || {});
  semNo = !estado.no;
  const t = no.temperature, h = no.relativeHumidity, vpd = no.vaporPressureDeficit;
  const solo = no.soilMoisture, lux = no.illuminance, luxFora = no.outdoorIlluminance;
  lampadasLigadas = no.lampState === 'ON';
  nevoaLigada = no.mistState === 'ON';

  const ct = corTemperatura(t, e), cv = corVpd(vpd), cs = corSolo(solo, e);
  pintar(mDht, ct);
  preencher(rot.dht, ct, 'DHT22 · ar', `${num(t)} °C`,
            `UR ${h == null ? '—' : num(h * 100, 0)} % · ${bola(cv)}VPD ${num(vpd, 2)} kPa`);
  pintar(mSolo, cs);
  preencher(rot.solo, cs, 'Sensor de solo', `${num(solo)} %`,
            `gotejamento liga < ${e.irrigationOnSoilMoisture} % · desliga ≥ ${e.irrigationOffSoilMoisture} %`);
  alvoMolhado = solo == null ? 0.5 : Math.min(1, Math.max(0, (solo - 25) / 25));   // terra e manchas mais escuras

  const ceuLux = luxFora != null ? luxFora : (lux == null ? null : lux / 0.68);     // sem o sensor do teto, estima
  const dia = ceuLux != null && ceuLux > NOITE_LUX;
  const cb = lampadasLigadas ? 'ouro' : dia ? 'amarelo' : 'cinza';
  pintar(mBh, cb);
  preencher(rot.bh, cb, 'BH1750 · dentro', `${num(lux == null ? null : lux / 1000)} klx`,
            lampadasLigadas ? (dia ? 'sol + lâmpadas' : 'lâmpadas') : dia ? 'sol · entra no DLI' : 'noite');
  preencher(rot.bhTeto, 'roxo', 'BH1750 · teto (lá fora)', `${num(luxFora == null ? null : luxFora / 1000)} klx`,
            dia ? 'só o sol · decide as lâmpadas' : 'noite');
  alvoLuz = ceuLux == null ? 1 : Math.min(1, Math.max(0, ceuLux / LUX_SOL));

  preencher(rot.lampadas, lampadasLigadas ? 'ouro' : 'cinza', `Lâmpadas LED · ${num(no.lampRatedPower, 0)} W`,
            lampadasLigadas ? 'Ligadas' : 'Desligadas',
            `ligam < ${num(e.lampOnOutdoorIlluminance / 1000, 0)} klx no teto · desligam > ` +
            `${num(e.lampOffOutdoorIlluminance / 1000, 0)} klx`);
  preencher(rot.nevoa, nevoaLigada ? 'nevoa' : 'cinza',
            `Nebulização · ${num(no.mistRatedPower, 0)} W · ${num(no.mistFlowRate, 0)} L/h`,
            nevoaLigada ? 'Ligada' : 'Desligada',
            `liga VPD ≥ ${num(e.mistOnVaporPressureDeficit, 2)} · desliga ≤ ${num(e.mistOffVaporPressureDeficit, 2)} kPa`);

  const ventOn = no.fanState === 'ON';
  alvoGiro = ventOn ? 16 : 0;
  preencher(rot.vent, ventOn ? 'verde' : 'cinza', `Exaustor · ${num(no.fanRatedPower, 0)} W`,
            ventOn ? 'Ligado' : 'Desligado', `liga ≥ ${e.fanOnTemperature} °C · desliga ≤ ${e.fanOffTemperature} °C`);

  bombaLigada = no.pumpState === 'ON';
  mat.tubo.color.setHex(bombaLigada ? 0x3ea8ff : 0x2b3036);
  preencher(rot.bomba, bombaLigada ? 'azul' : 'cinza', `Gotejamento · bomba ${num(no.pumpRatedPower, 0)} W`,
            `${bombaLigada ? 'Ligada' : 'Desligada'} · ${num(no.waterFlow)} L/min`,
            bombaLigada && no.waterFlow != null && no.waterFlow < 0.5 * (no.pumpFlowRate || 1500) / 60
              ? 'vazão baixa: caixa vazia ou cano entupido?' : '');

  const capacidade = no.tankCapacity || 500, litros = no.tankWaterVolume;
  const fracaoCaixa = litros == null ? 0 : Math.min(1, Math.max(0, litros / capacidade));
  const cc = litros == null ? 'cinza' : fracaoCaixa < RESERVA[0] ? 'vermelho' : fracaoCaixa < RESERVA[1] ? 'laranja' : 'verde';
  pintar(mCaixa, cc);
  preencher(rot.caixa, cc, `Caixa d'água · ${num(capacidade, 0)} L`, `${num(litros, 0)} L`,
            `${num(fracaoCaixa * 100, 0)} % · ultrassom na tampa`);
  alvoAgua = fracaoCaixa;

  ultimaMedida = no.TimeInstant ? new Date(no.TimeInstant).toLocaleTimeString('pt-BR') : null;
  rot.esp.style.borderTopColor = CSS.verde;
  rot.esp.innerHTML = `<b>ESP32-001 · nó</b><div class="s">${ultimaMedida ? 'medida das ' + ultimaMedida : 'sem medidas ainda'}</div>`;
  led.material.emissiveIntensity = 3;

  preencher(rot.fora, 'roxo', `Lá fora · ${escapar(clima.source || 'sem leitura')}`, `${num(clima.temperature)} °C`,
            `UR ${clima.relativeHumidity == null ? '—' : num(clima.relativeHumidity * 100, 0)} %`);

  if (primeira) {                                   // ao abrir a página, já começa no estado certo
    luzAtual = alvoLuz;
    giro = alvoGiro;
    nivel = alvoAgua;
    molhado = alvoMolhado;
    brilhoLed = lampadasLigadas ? 1 : 0;
    primeira = false;
  }
}

function mostrarStatus() {
  const el = document.getElementById('status');
  if (falha) {
    el.innerHTML = `<span class="ponto" style="background:${CSS.vermelho}"></span>Sem resposta do Orion: ${escapar(falha)}`;
  } else if (semNo) {
    el.innerHTML = `<span class="ponto" style="background:${CSS.laranja}"></span>A ESP32 ainda não mandou medidas. ` +
                   `Rode <b>bash estufa/subir.sh</b>.`;
  } else if (ultimaResposta) {
    const s = Math.round((Date.now() - ultimaResposta) / 1000);
    el.innerHTML = `<span class="ponto" style="background:${CSS.verde}"></span>Orion respondeu há ${s} s` +
                   (ultimaMedida ? ` · medida das ${ultimaMedida}` : '');
  }
}

async function atualizar() {
  try {
    const resposta = await fetch('api/estado', { cache: 'no-store' });
    const estado = await resposta.json();
    if (!resposta.ok) throw new Error(estado.erro || `HTTP ${resposta.status}`);
    aplicar(estado);
    ultimaResposta = Date.now();
    falha = null;
  } catch (erro) {
    falha = erro.message;
  }
  mostrarStatus();
}
atualizar();
setInterval(atualizar, 5000);
setInterval(mostrarStatus, 1000);

// link para o painel: no Codespace, troca a porta 3003 pela 3002 no endereço
const link = document.getElementById('link-painel');
link.href = location.host.includes('-3003.')
  ? `${location.protocol}//${location.host.replace('-3003.', '-3002.')}/`
  : `${location.protocol}//${location.hostname}:3002/`;

// --- animação ------------------------------------------------------------------------------
const relogio = new THREE.Clock();
function aplicarLuz(f) {
  sol.intensity = 0.12 + 2.5 * f;
  ceu.intensity = 0.25 + 0.75 * f;
  cena.background.copy(CEU_NOITE).lerp(CEU_DIA, f);
  cena.fog.color.copy(cena.background);
}
renderer.setAnimationLoop(() => {
  const dt = Math.min(relogio.getDelta(), 0.05), t = relogio.elapsedTime;
  luzAtual += (alvoLuz - luzAtual) * Math.min(1, dt * 0.8);
  aplicarLuz(luzAtual);
  giro += (alvoGiro - giro) * Math.min(1, dt * 1.2);
  nivel += (alvoAgua - nivel) * Math.min(1, dt * 1.5);
  const hAgua = Math.max(0.005, CAIXA.hAgua * nivel);
  agua.scale.y = hAgua;
  agua.position.y = 0.02 + hAgua / 2;
  rotor.rotation.x -= giro * dt;
  mat.tubo.emissiveIntensity = bombaLigada ? 0.55 + 0.35 * Math.sin(t * 5) : Math.max(0, mat.tubo.emissiveIntensity - dt);
  luzBomba.material.emissiveIntensity = bombaLigada ? 1.8 : 0.05;
  molhado += (alvoMolhado - molhado) * Math.min(1, dt * 1.5);
  mat.terra.color.copy(TERRA_SECA).lerp(TERRA_MOLHADA, molhado);
  desenharGotejadores(molhado, bombaLigada, t);
  brilhoLed += ((lampadasLigadas ? 1 : 0) - brilhoLed) * Math.min(1, dt * 4);
  mat.led.emissiveIntensity = 2.4 * brilhoLed;
  for (const p of luzesLed) p.intensity = 4.5 * brilhoLed;
  mat.tuboNevoa.emissiveIntensity = nevoaLigada ? 0.45 + 0.25 * Math.sin(t * 4)
                                                : Math.max(0, mat.tuboNevoa.emissiveIntensity - dt);
  animarNevoa(nevoaLigada, dt);
  led.material.emissiveIntensity = Math.max(0.1, led.material.emissiveIntensity - dt * 3);
  for (const m of marcadores) m.scale.setScalar(1 + 0.12 * Math.sin(t * 3 + m.position.x));
  controles.update();
  renderer.render(cena, camera);
  camadaRotulos.render(cena, camera);
  arrumarRotulos(t);
});

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  camadaRotulos.setSize(innerWidth, innerHeight);
  nevoa.material.uniforms.escala.value = escalaPontos();
});

# three.js 0.187.0 (MIT)

`three-0.187.0.min.js` é o three.js 0.187.0 (pacote `three` do npm) com dois módulos de
exemplo, `OrbitControls` e `CSS2DRenderer`, num único arquivo ES module minificado:

```bash
npm pack three@0.187.0 && tar -xzf three-0.187.0.tgz
cat > entrada.js <<'X'
export * from './package/build/three.module.js';
export { OrbitControls } from './package/examples/jsm/controls/OrbitControls.js';
export { CSS2DRenderer, CSS2DObject } from './package/examples/jsm/renderers/CSS2DRenderer.js';
X
npx esbuild@0.24 entrada.js --bundle --format=esm --minify --legal-comments=eof \
  --alias:three=./package/build/three.module.js --outfile=three-0.187.0.min.js
```

Fica no repositório para a página funcionar sem depender de CDN. Licença em `LICENSE-three.txt`.

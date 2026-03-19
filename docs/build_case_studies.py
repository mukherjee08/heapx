#!/usr/bin/env python3
"""
Build script for heapx case study pages.

Scans case-studies/*/README.md, generates:
  - docs/case-studies/{name}.html  (one per case study with embedded README)
  - docs/case-studies/index.json   (listing for index.html to consume)

Removes stale .html files for deleted case studies.
Run from repo root: python3 docs/build_case_studies.py
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASE_STUDIES_SRC = os.path.join(REPO_ROOT, "case-studies")
CASE_STUDIES_DOCS = os.path.join(REPO_ROOT, "docs", "case-studies")
GITHUB_BASE = "https://github.com/mukherjee08/heapx/tree/main/case-studies"
GITHUB_RAW = "https://raw.githubusercontent.com/mukherjee08/heapx/main/case-studies"


def dir_to_display_name(dirname):
    """Convert 'Financial_Order-Book-Simulation' to 'Financial Order-Book Simulation'."""
    return dirname.replace("_", " ")


def rewrite_image_urls(md_content, dirname):
    """Rewrite relative image paths to absolute GitHub raw URLs."""
    def replace_img(m):
        alt, path = m.group(1), m.group(2)
        if path.startswith("http://") or path.startswith("https://"):
            return m.group(0)
        clean = path.lstrip("./")
        return f"![{alt}]({GITHUB_RAW}/{dirname}/{clean})"
    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_img, md_content)


def generate_html(dirname, display_name, md_content):
    """Generate a case study HTML page with embedded README."""
    escaped = json.dumps(md_content)
    source_url = f"{GITHUB_BASE}/{dirname}"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>heapx — {display_name}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90' fill='%23d4a0b0'>Σ</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/python.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/bash.min.js"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/languages/c.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html{{font-size:16px;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}}
html,body{{width:100%;height:100%;background:#000;overflow:hidden}}
body{{font-family:'Inter',system-ui,-apple-system,sans-serif;color:rgba(255,255,255,.92);line-height:1.7}}
canvas#bg{{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0}}
#content{{position:relative;z-index:1;overflow-x:hidden;overflow-y:auto;height:100%;-webkit-overflow-scrolling:touch}}
#content::-webkit-scrollbar{{width:6px}}
#content::-webkit-scrollbar-track{{background:transparent}}
#content::-webkit-scrollbar-thumb{{background:rgba(255,255,255,.15);border-radius:3px}}
nav{{position:fixed;top:0;left:0;right:0;z-index:100;padding:0 48px;height:72px;display:flex;align-items:center;justify-content:space-between;backdrop-filter:blur(40px) saturate(1.8);-webkit-backdrop-filter:blur(40px) saturate(1.8);background:rgba(0,0,0,.55);border-bottom:1px solid rgba(255,255,255,.08);transition:all .4s ease}}
nav .logo{{font-size:1.4rem;font-weight:600;letter-spacing:-.02em;color:#fff;text-decoration:none;cursor:pointer;transition:all .4s ease}}
nav .logo span{{color:rgba(255,255,255,.4);font-weight:400}}
nav .links{{display:flex;gap:32px;align-items:center;transition:all .4s ease}}
nav .links a{{color:rgba(255,255,255,.6);text-decoration:none;font-size:1.0rem;font-weight:500;transition:all .2s}}
nav .links a:hover{{color:#fff}}
nav .links a.cta{{background:rgba(255,255,255,.12);padding:8px 22px;border-radius:20px;color:rgba(255,255,255,.9);border:1px solid rgba(255,255,255,.1);transition:all .2s}}
nav .links a.cta:hover{{background:rgba(255,255,255,.2);color:#fff}}
nav.scrolled{{background:transparent;border-bottom-color:transparent;backdrop-filter:none;-webkit-backdrop-filter:none}}
nav.scrolled .logo{{background:rgba(0,0,0,.55);backdrop-filter:blur(40px) saturate(1.8);-webkit-backdrop-filter:blur(40px) saturate(1.8);padding:8px 20px;border-radius:14px;border:1px solid rgba(255,255,255,.1);transition:all .2s}}
nav.scrolled .logo:hover{{background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.18);color:#fff}}
nav.scrolled .links a.cta{{background:rgba(0,0,0,.55);backdrop-filter:blur(40px) saturate(1.8);-webkit-backdrop-filter:blur(40px) saturate(1.8);border:1px solid rgba(255,255,255,.1);transition:all .2s}}
nav.scrolled .links a.cta:hover{{background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.18);color:#fff}}
.readme-wrap{{padding:140px 48px 100px;max-width:1120px;margin:0 auto}}
.md h1{{font-size:clamp(2.2rem,4.5vw,3.2rem);font-weight:700;letter-spacing:-.03em;line-height:1.15;margin:64px 0 24px;background:linear-gradient(135deg,#fff 0%,rgba(255,255,255,.7) 50%,rgba(200,180,255,.6) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.md h1:first-child{{margin-top:0}}
.md h2{{font-size:clamp(1.6rem,3vw,2.2rem);font-weight:700;letter-spacing:-.02em;margin:56px 0 20px;color:rgba(255,255,255,.9);padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,.08)}}
.md h3{{font-size:clamp(1.3rem,2.5vw,1.75rem);font-weight:600;letter-spacing:-.01em;margin:40px 0 16px;color:rgba(255,255,255,.85)}}
.md h4{{font-size:clamp(1.1rem,2vw,1.5rem);font-weight:600;margin:32px 0 12px;color:rgba(255,255,255,.8)}}
.md p{{font-size:clamp(1rem,2vw,1.35rem);color:rgba(255,255,255,.55);line-height:1.7;margin:0 0 16px;font-weight:300}}
.md strong{{color:rgba(255,255,255,.8);font-weight:600}}
.md a{{color:rgba(200,180,255,.7);text-decoration:none;border-bottom:1px solid rgba(200,180,255,.2);transition:all .2s}}
.md a:hover{{color:rgba(200,180,255,1);border-bottom-color:rgba(200,180,255,.5)}}
.md ul,.md ol{{margin:0 0 16px 24px;color:rgba(255,255,255,.55);font-size:clamp(1rem,2vw,1.35rem);font-weight:300}}
.md li{{margin-bottom:6px;line-height:1.6}}
.md code{{font-family:'JetBrains Mono',monospace;font-size:.88em;background:rgba(255,255,255,.07);padding:2px 7px;border-radius:5px;color:rgba(200,180,255,.75)}}
.md pre{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:28px 32px;overflow-x:auto;font-family:'JetBrains Mono',monospace;font-size:clamp(.95rem,1.8vw,1.2rem);line-height:1.7;color:rgba(255,255,255,.7);margin:24px 0 28px}}
.md pre code{{background:none;padding:0;border-radius:0;font-size:inherit;color:inherit}}
.hljs-keyword,.hljs-built_in,.hljs-type,.hljs-literal,.hljs-selector-tag{{color:rgba(200,180,255,.8)}}
.hljs-function .hljs-title,.hljs-title.function_,.hljs-title.class_{{color:rgba(130,200,255,.8)}}
.hljs-string,.hljs-doctag{{color:rgba(160,220,150,.8)}}
.hljs-comment{{color:rgba(255,255,255,.25)}}
.hljs-number{{color:rgba(255,190,130,.8)}}
.hljs-variable,.hljs-params,.hljs-attr{{color:rgba(255,255,255,.7)}}
.hljs-meta,.hljs-meta .hljs-keyword{{color:rgba(200,180,255,.6)}}
.hljs-operator,.hljs-punctuation{{color:rgba(255,255,255,.5)}}
.md table{{width:100%;border-collapse:collapse;margin:24px 0;font-size:clamp(1rem,2vw,1.35rem)}}
.md th{{text-align:left;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.12);color:rgba(255,255,255,.5);font-weight:600;font-size:clamp(.85rem,1.5vw,1.05rem);letter-spacing:.04em;text-transform:uppercase}}
.md td{{padding:12px 16px;border-bottom:1px solid rgba(255,255,255,.05);color:rgba(255,255,255,.55);font-weight:300}}
.md td code{{font-size:.88em}}
.md tr:hover td{{background:rgba(255,255,255,.03)}}
.md blockquote{{border-left:3px solid rgba(200,180,255,.3);padding:8px 20px;margin:16px 0;color:rgba(255,255,255,.45);font-style:italic;font-size:clamp(1rem,2vw,1.35rem)}}
.md hr{{border:none;border-top:1px solid rgba(255,255,255,.08);margin:48px 0}}
.md img{{max-width:100%;border-radius:8px}}
footer{{padding:48px;text-align:center;border-top:1px solid rgba(255,255,255,.06);margin-top:80px}}
footer p{{font-size:.8rem;color:rgba(255,255,255,.25)}}
footer a{{color:rgba(255,255,255,.4);text-decoration:none}}
footer a:hover{{color:rgba(255,255,255,.7)}}
footer .footer-links{{display:flex;gap:24px;justify-content:center;margin-bottom:16px}}
@media(max-width:768px){{
  nav{{padding:0 20px}}
  nav.scrolled .logo{{padding:6px 14px;font-size:1.1rem}}
  .readme-wrap{{padding:100px 20px 60px}}
}}
</style>
</head>
<body>
<canvas id="bg"></canvas>
<nav id="navbar">
  <a href="../index.html" class="logo">heapx<span>.py</span></a>
  <div class="links">
    <a href="{source_url}" class="cta" target="_blank">Source Code</a>
  </div>
</nav>
<div id="content">
<div class="readme-wrap">
  <div id="readme" class="md"></div>
</div>
<footer>
  <div class="footer-links">
    <a href="https://pypi.org/project/heapx/" target="_blank">PyPI</a>
    <a href="https://anaconda.org/conda-forge/heapx" target="_blank">Anaconda</a>
    <a href="https://github.com/mukherjee08/heapx" target="_blank">GitHub</a>
    <a href="https://github.com/mukherjee08/heapx/blob/main/LICENSE" target="_blank">MIT License</a>
  </div>
  <p>&copy; <span id="year"></span> Aniruddha Mukherjee &middot; <a href="mailto:mukherjee08@outlook.com">mukherjee08@outlook.com</a></p>
</footer>
</div>

<script>document.getElementById('year').textContent=new Date().getFullYear();</script>
<script>
(function(){{
  var nav=document.getElementById('navbar');
  var content=document.getElementById('content');
  content.addEventListener('scroll',function(){{
    if(content.scrollTop>80){{nav.classList.add('scrolled')}}else{{nav.classList.remove('scrolled')}}
  }});
}})();
</script>
<script>
(function(){{
  var md={escaped};
  var renderer=new marked.Renderer();
  renderer.heading=function(text,level){{
    var slug=text.toLowerCase().replace(/<[^>]*>/g,'').replace(/`/g,'').replace(/[^\\w]+/g,'-').replace(/^-+|-+$/g,'');
    return '<h'+level+' id="'+slug+'">'+text+'</h'+level+'>\\n';
  }};
  document.getElementById('readme').innerHTML=marked.parse(md,{{renderer:renderer,highlight:function(code,lang){{if(lang&&hljs.getLanguage(lang))return hljs.highlight(code,{{language:lang}}).value;return hljs.highlightAuto(code).value;}}}});
  var content=document.getElementById('content');
  document.querySelectorAll('.md a[href^="#"]').forEach(function(a){{
    a.addEventListener('click',function(e){{
      e.preventDefault();
      var id=this.getAttribute('href').slice(1);
      var target=document.getElementById(id);
      if(target){{content.scrollTo({{top:target.offsetTop-100,behavior:'smooth'}})}}
    }});
  }});
}})();
</script>
<script>
(function(){{
  var canvas=document.getElementById('bg');var gl=canvas.getContext('webgl');if(!gl)return;
  var vs='attribute vec2 a_pos;void main(){{gl_Position=vec4(a_pos,0,1);}}';
  var fs=`precision highp float;uniform vec2 u_res;uniform float u_time;uniform vec2 u_mouse;vec3 mod289(vec3 x){{return x-floor(x*(1./289.))*289.;}}vec2 mod289(vec2 x){{return x-floor(x*(1./289.))*289.;}}vec3 permute(vec3 x){{return mod289(((x*34.)+1.)*x);}}float snoise(vec2 v){{const vec4 C=vec4(.211324865405187,.366025403784439,-.577350269189626,.024390243902439);vec2 i=floor(v+dot(v,C.yy));vec2 x0=v-i+dot(i,C.xx);vec2 i1=(x0.x>x0.y)?vec2(1,0):vec2(0,1);vec4 x12=x0.xyxy+C.xxzz;x12.xy-=i1;i=mod289(i);vec3 p=permute(permute(i.y+vec3(0,i1.y,1.))+i.x+vec3(0,i1.x,1.));vec3 m=max(.5-vec3(dot(x0,x0),dot(x12.xy,x12.xy),dot(x12.zw,x12.zw)),0.);m=m*m;m=m*m;vec3 x=2.*fract(p*C.www)-1.;vec3 h=abs(x)-.5;vec3 ox=floor(x+.5);vec3 a0=x-ox;m*=1.79284291400159-.85373472095314*(a0*a0+h*h);vec3 g;g.x=a0.x*x0.x+h.x*x0.y;g.yz=a0.yz*x12.xz+h.yz*x12.yw;return 130.*dot(m,g);}}void main(){{vec2 uv=(gl_FragCoord.xy-.5*u_res)/min(u_res.x,u_res.y);float t=u_time*.12;vec2 mouse=(u_mouse-.5*u_res)/min(u_res.x,u_res.y);float mouseDist=length(uv-mouse);float mouseInf=smoothstep(1.2,0.,mouseDist)*.18;float n1=snoise(uv*.8+vec2(t*.4,t*.3));float n2=snoise(uv*1.1-vec2(t*.3,t*.5));float n3=snoise(uv*.6+vec2(n1,n2)*.3+mouse*.2);vec2 distort=vec2(n1,n2)*.07+vec2(n3)*.05;distort+=mouseInf*normalize(uv-mouse+.001)*.1;vec2 st=uv+distort;vec3 base=vec3(.04,.02,.06);vec3 c1=vec3(.55,.08,.35);vec3 c2=vec3(.05,.35,.45);vec3 c3=vec3(.5,.15,.55);vec3 c4=vec3(.08,.22,.38);vec3 c5=vec3(.55,.25,.1);float w1=snoise(st*.9+t*.25)*.5+.5;float w2=snoise(st*1.1-t*.2+3.)*.5+.5;float w3=snoise(st*.7+t*.3+7.)*.5+.5;vec3 col=mix(c1,c2,w1);col=mix(col,c3,w2*.5);col=mix(col,c4,w3*.4);col=mix(col,c5,smoothstep(.35,.65,snoise(st*1.2+t*.15+11.))*.25);float intensity=smoothstep(-.3,.6,snoise(st*.7+t*.18+5.))*.45+.15;col=mix(base,col,intensity);col+=vec3(.3,.12,.25)*mouseInf;float vig=1.-dot(uv*.55,uv*.55);col*=smoothstep(0.,1.,vig);gl_FragColor=vec4(col,1.);}}`;
  function compile(type,src){{var s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){{console.error(gl.getShaderInfoLog(s));return null;}}return s;}}
  var prog=gl.createProgram();gl.attachShader(prog,compile(gl.VERTEX_SHADER,vs));gl.attachShader(prog,compile(gl.FRAGMENT_SHADER,fs));gl.linkProgram(prog);gl.useProgram(prog);
  var buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),gl.STATIC_DRAW);var pos=gl.getAttribLocation(prog,'a_pos');gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,0,0);
  var uRes=gl.getUniformLocation(prog,'u_res');var uTime=gl.getUniformLocation(prog,'u_time');var uMouse=gl.getUniformLocation(prog,'u_mouse');
  var mx=0,my=0,tmx=0,tmy=0;window.addEventListener('mousemove',function(e){{tmx=e.clientX;tmy=e.clientY;}});window.addEventListener('touchmove',function(e){{e.preventDefault();tmx=e.touches[0].clientX;tmy=e.touches[0].clientY;}},{{passive:false}});
  function resize(){{var dpr=window.devicePixelRatio||1;canvas.width=window.innerWidth*dpr;canvas.height=window.innerHeight*dpr;}}window.addEventListener('resize',resize);resize();
  var t0=performance.now();(function loop(){{mx+=(tmx*(window.devicePixelRatio||1)-mx)*.03;my+=((window.innerHeight-tmy)*(window.devicePixelRatio||1)-my)*.03;gl.viewport(0,0,canvas.width,canvas.height);gl.uniform2f(uRes,canvas.width,canvas.height);gl.uniform1f(uTime,(performance.now()-t0)/1000);gl.uniform2f(uMouse,mx,my);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);requestAnimationFrame(loop);}})();
}})();
</script>
</body>
</html>'''


def main():
    os.makedirs(CASE_STUDIES_DOCS, exist_ok=True)

    # Scan case studies
    studies = []
    if os.path.isdir(CASE_STUDIES_SRC):
        for dirname in sorted(os.listdir(CASE_STUDIES_SRC)):
            dirpath = os.path.join(CASE_STUDIES_SRC, dirname)
            readme = os.path.join(dirpath, "README.md")
            if os.path.isdir(dirpath) and os.path.isfile(readme):
                studies.append(dirname)

    # Generate HTML pages
    generated = set()
    for dirname in studies:
        readme_path = os.path.join(CASE_STUDIES_SRC, dirname, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        md_content = rewrite_image_urls(md_content, dirname)
        display_name = dir_to_display_name(dirname)
        html = generate_html(dirname, display_name, md_content)

        out_path = os.path.join(CASE_STUDIES_DOCS, f"{dirname}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        generated.add(f"{dirname}.html")
        print(f"  Generated: case-studies/{dirname}.html")

    # Remove stale HTML files
    removed = 0
    for fname in os.listdir(CASE_STUDIES_DOCS):
        if fname.endswith(".html") and fname not in generated:
            os.remove(os.path.join(CASE_STUDIES_DOCS, fname))
            removed += 1
            print(f"  Removed stale: case-studies/{fname}")

    # Generate index.json
    index = [{"dir": d, "name": dir_to_display_name(d)} for d in studies]
    index_path = os.path.join(CASE_STUDIES_DOCS, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    # Patch index.html with embedded case study list
    index_html_path = os.path.join(REPO_ROOT, "docs", "index.html")
    if os.path.isfile(index_html_path):
        with open(index_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        embedded = f"var studies={json.dumps(index)};"
        import re as _re
        patched = _re.sub(
            r'/\* CASE_STUDIES_DATA:BEGIN \*/.*?/\* CASE_STUDIES_DATA:END \*/',
            f'/* CASE_STUDIES_DATA:BEGIN */{embedded}/* CASE_STUDIES_DATA:END */',
            html
        )
        with open(index_html_path, "w", encoding="utf-8") as f:
            f.write(patched)
        print(f"  Patched index.html with {len(index)} case studies.")

    print(f"\nDone. Generated {len(studies)} pages. Removed {removed} stale.")


if __name__ == "__main__":
    main()

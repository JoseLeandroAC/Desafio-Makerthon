"""
Verificação simples de imagens em imagens_conhecidas/*/* para detectar se há um rosto claro
usando o classificador Haarcascade do OpenCV. Lista arquivos que não tiveram rostos detectados.

Uso:
  python tools\check_images_faces.py
  python tools\check_images_faces.py --min-size 30  --report bad_images.txt

Dependências: OpenCV (`cv2`) — já usada pelo projeto.
"""
import os
from pathlib import Path
import cv2
import argparse

parser = argparse.ArgumentParser(description='Verifica presença de rostos em imagens_conhecidas')
parser.add_argument('--root', default='imagens_conhecidas', help='pasta com subpastas por pessoa')
parser.add_argument('--min-size', type=int, default=30, help='tamanho mínimo do rosto detectado (pixels)')
parser.add_argument('--report', default=None, help='arquivo para salvar lista de imagens sem rosto')
args = parser.parse_args()

cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
if not os.path.exists(cascade_path):
    print('Não foi possível localizar o Haarcascade do OpenCV em:', cascade_path)
    raise SystemExit(1)

cascade = cv2.CascadeClassifier(cascade_path)

root = Path(args.root)
if not root.exists():
    print(f"Pasta {root} não encontrada. Execute este script a partir do diretório do projeto.")
    raise SystemExit(1)

exts = ('.jpg', '.jpeg', '.png', '.bmp')
problematic = []
total = 0
with_report = []

for p in root.rglob('*'):
    if p.is_file() and p.suffix.lower() in exts:
        total += 1
        img = cv2.imread(str(p))
        if img is None:
            print(f'[ERRO] Não foi possível ler {p}')
            problematic.append(str(p))
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(args.min_size, args.min_size))
        if len(faces) == 0:
            print(f'[SEM ROSTO] {p}')
            problematic.append(str(p))
        else:
            print(f'[OK] {p}  -> {len(faces)} face(s) detectada(s)')

print('\nResumo:')
print(f'  total de imagens verificadas: {total}')
print(f'  imagens sem rosto detectado: {len(problematic)}')

if args.report:
    try:
        with open(args.report, 'w', encoding='utf-8') as f:
            for item in problematic:
                f.write(item + '\n')
        print(f'Relatório salvo em {args.report}')
    except Exception as e:
        print('Falha ao gravar relatório:', e)

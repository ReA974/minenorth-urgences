"""Synthétise la sirène 2 tons française (435 / 580 Hz, 0,55 s par ton, boucle de 4,4 s) -> assets/<pack>/sounds/siren_fr_2tons.ogg
usage : python siren.py [dossier_sortie]   (pip install numpy soundfile)"""
import os, sys
import numpy as np, soundfile as sf
sr = 44100
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'minenorthpolicecar', 'sounds')


def tone(f, d):
    t = np.arange(int(sr * d)) / sr
    w = np.tanh(1.8 * (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)))
    a = int(sr * 0.012); env = np.ones(len(t)); env[:a] = np.linspace(0, 1, a); env[-a:] = np.linspace(1, 0, a)
    return w * env


seq = np.concatenate([tone(435, 0.55), tone(580, 0.55)] * 4)
seq = seq / np.abs(seq).max() * 0.8
os.makedirs(out, exist_ok=True)
sf.write(os.path.join(out, 'siren_fr_2tons.ogg'), seq.astype('float32'), sr, format='OGG', subtype='VORBIS')

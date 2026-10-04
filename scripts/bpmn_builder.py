"""
Tiny BPMN 2.0 builder: describe a process as lanes, nodes and flows, and get
  1. a standards-compliant .bpmn file (with diagram interchange), which opens in
     bpmn.io / Camunda Modeler / Signavio, and
  2. a matching .svg picture for READMEs.

Layout is a simple grid: each node sits in a lane (row) and a column.
"""
from xml.sax.saxutils import escape
import textwrap

COL_W, LANE_H, HEAD_W, PAD = 150, 130, 34, 20
SIZES = {"start": (36, 36), "end": (36, 36), "task": (116, 68), "xor": (50, 50)}


class Process:
    def __init__(self, pid, name, lanes):
        self.pid, self.name, self.lanes = pid, name, lanes
        self.nodes, self.flows, self.notes = {}, [], []

    def node(self, nid, kind, label, lane, col, issue=False):
        self.nodes[nid] = dict(id=nid, kind=kind, label=label, lane=lane, col=col, issue=issue)
        return self

    def flow(self, src, dst, label="", route=None):
        """route: None (automatic), 'elbow' (right then down/up into the target's top/bottom)
        or 'vertical' (leave from top/bottom, then across into the target's left side)."""
        self.flows.append(dict(id=f"F_{src}_{dst}", src=src, dst=dst, label=label, route=route))
        return self

    # ------------------------------------------------------------ geometry
    def _dims(self):
        ncols = max(n["col"] for n in self.nodes.values()) + 1
        width = HEAD_W + PAD + ncols * COL_W + PAD
        height = len(self.lanes) * LANE_H
        return width, height

    def _box(self, n):
        w, h = SIZES[n["kind"]]
        li = self.lanes.index(n["lane"])
        cx = HEAD_W + PAD + n["col"] * COL_W + COL_W / 2
        cy = li * LANE_H + LANE_H / 2
        return cx - w / 2, cy - h / 2, w, h

    def _route(self, f):
        a, b = self.nodes[f["src"]], self.nodes[f["dst"]]
        ax, ay, aw, ah = self._box(a)
        bx, by, bw, bh = self._box(b)
        acx, acy, bcx, bcy = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2
        if f.get("route") == "elbow":
            ty = by if bcy > acy else by + bh
            return [(ax + aw, acy), (bcx, acy), (bcx, ty)]
        if f.get("route") == "vertical" or (a["kind"] == "xor" and b["col"] > a["col"] and abs(acy - bcy) > 1
                                             and f.get("route") is None and not self._has_right_exit(f)):
            sy = ay if bcy < acy else ay + ah
            return [(acx, sy), (acx, bcy), (bx, bcy)]
        if b["col"] > a["col"]:
            if abs(acy - bcy) < 1:
                return [(ax + aw, acy), (bx, bcy)]
            if b["col"] == a["col"] + 1 or a["kind"] != "xor":
                mx = (ax + aw + bx) / 2
                return [(ax + aw, acy), (mx, acy), (mx, bcy), (bx, bcy)]
            # gateway branching to a later column in another lane: leave from top/bottom
            sy = ay if bcy < acy else ay + ah
            return [(acx, sy), (acx, bcy), (bx, bcy)]
        if b["col"] == a["col"]:
            sy, ty = (ay + ah, by) if bcy > acy else (ay, by + bh)
            return [(acx, sy), (bcx, ty)]
        # loop back to an earlier column: travel along the bottom edge of the lower lane
        low = max(self.lanes.index(a["lane"]), self.lanes.index(b["lane"]))
        y = (low + 1) * LANE_H - 14
        return [(acx, ay + ah), (acx, y), (bcx, y), (bcx, by + bh)]

    def _has_right_exit(self, f):
        """A gateway keeps its right-hand exit for the first cross-lane flow when no
        same-lane flow uses it; later cross-lane flows leave vertically."""
        sibs = [g for g in self.flows if g["src"] == f["src"]]
        a = self.nodes[f["src"]]
        same_lane = any(self.nodes[g["dst"]]["lane"] == a["lane"] for g in sibs)
        if same_lane:
            return False
        cross = [g for g in sibs if self.nodes[g["dst"]]["lane"] != a["lane"] and g.get("route") is None]
        return bool(cross) and cross[0] is f

    # ------------------------------------------------------------ BPMN XML
    def to_bpmn(self):
        tag = {"start": "startEvent", "end": "endEvent", "task": "userTask", "xor": "exclusiveGateway"}
        incoming = {k: [] for k in self.nodes}
        outgoing = {k: [] for k in self.nodes}
        for f in self.flows:
            outgoing[f["src"]].append(f["id"]); incoming[f["dst"]].append(f["id"])
        width, height = self._dims()
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" '
               'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
               'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
               'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
               f'id="Defs_{self.pid}" targetNamespace="https://github.com/chiamakaikpo">',
               f'  <bpmn:collaboration id="Collab_{self.pid}">',
               f'    <bpmn:participant id="Pool_{self.pid}" name="{escape(self.name)}" processRef="{self.pid}"/>',
               '  </bpmn:collaboration>',
               f'  <bpmn:process id="{self.pid}" isExecutable="false">',
               '    <bpmn:laneSet id="LaneSet_1">']
        for i, lane in enumerate(self.lanes):
            out.append(f'      <bpmn:lane id="Lane_{i}" name="{escape(lane)}">')
            for n in self.nodes.values():
                if n["lane"] == lane:
                    out.append(f'        <bpmn:flowNodeRef>{n["id"]}</bpmn:flowNodeRef>')
            out.append('      </bpmn:lane>')
        out.append('    </bpmn:laneSet>')
        for n in self.nodes.values():
            out.append(f'    <bpmn:{tag[n["kind"]]} id="{n["id"]}" name="{escape(n["label"])}">')
            out += [f'      <bpmn:incoming>{x}</bpmn:incoming>' for x in incoming[n["id"]]]
            out += [f'      <bpmn:outgoing>{x}</bpmn:outgoing>' for x in outgoing[n["id"]]]
            out.append(f'    </bpmn:{tag[n["kind"]]}>')
        for f in self.flows:
            name = f' name="{escape(f["label"])}"' if f["label"] else ""
            out.append(f'    <bpmn:sequenceFlow id="{f["id"]}"{name} sourceRef="{f["src"]}" targetRef="{f["dst"]}"/>')
        out.append('  </bpmn:process>')
        out.append(f'  <bpmndi:BPMNDiagram id="Diagram_{self.pid}">')
        out.append(f'    <bpmndi:BPMNPlane id="Plane_{self.pid}" bpmnElement="Collab_{self.pid}">')
        out.append(f'      <bpmndi:BPMNShape id="Pool_{self.pid}_di" bpmnElement="Pool_{self.pid}" isHorizontal="true">'
                   f'<dc:Bounds x="0" y="0" width="{width}" height="{height}"/></bpmndi:BPMNShape>')
        for i, _ in enumerate(self.lanes):
            out.append(f'      <bpmndi:BPMNShape id="Lane_{i}_di" bpmnElement="Lane_{i}" isHorizontal="true">'
                       f'<dc:Bounds x="{HEAD_W}" y="{i * LANE_H}" width="{width - HEAD_W}" height="{LANE_H}"/></bpmndi:BPMNShape>')
        for n in self.nodes.values():
            x, y, w, h = self._box(n)
            marker = ' isMarkerVisible="true"' if n["kind"] == "xor" else ""
            out.append(f'      <bpmndi:BPMNShape id="{n["id"]}_di" bpmnElement="{n["id"]}"{marker}>'
                       f'<dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{w}" height="{h}"/></bpmndi:BPMNShape>')
        for f in self.flows:
            pts = "".join(f'<di:waypoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in self._route(f))
            out.append(f'      <bpmndi:BPMNEdge id="{f["id"]}_di" bpmnElement="{f["id"]}">{pts}</bpmndi:BPMNEdge>')
        out += ['    </bpmndi:BPMNPlane>', '  </bpmndi:BPMNDiagram>', '</bpmn:definitions>', '']
        return "\n".join(out)

    # ------------------------------------------------------------ SVG
    def to_svg(self, title, subtitle=""):
        width, height = self._dims()
        top = 64
        W, H = width + 2, height + top + 40
        s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Arial, sans-serif">',
             '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M0,0 L10,5 L0,10 z" fill="#3a4654"/></marker></defs>',
             f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
             f'<text x="1" y="26" font-size="18" font-weight="700" fill="#18212c">{escape(title)}</text>',
             f'<text x="1" y="46" font-size="12" fill="#5b6878">{escape(subtitle)}</text>',
             f'<g transform="translate(1,{top})">',
             f'<rect x="0" y="0" width="{width}" height="{height}" fill="none" stroke="#3a4654" stroke-width="1.5"/>']
        for i, lane in enumerate(self.lanes):
            y = i * LANE_H
            fill = "#f6f8fb" if i % 2 == 0 else "#ffffff"
            s.append(f'<rect x="{HEAD_W}" y="{y}" width="{width - HEAD_W}" height="{LANE_H}" fill="{fill}" stroke="#c4ccd6"/>')
            s.append(f'<rect x="0" y="{y}" width="{HEAD_W}" height="{LANE_H}" fill="#e8edf4" stroke="#c4ccd6"/>')
            cx, cy = HEAD_W / 2, y + LANE_H / 2
            s.append(f'<text x="{cx}" y="{cy}" font-size="11" font-weight="600" fill="#2b3440" text-anchor="middle" '
                     f'dominant-baseline="middle" transform="rotate(-90 {cx} {cy})">{escape(lane)}</text>')
        for f in self.flows:
            pts = self._route(f)
            d = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
            s.append(f'<polyline points="{d}" fill="none" stroke="#3a4654" stroke-width="1.4" marker-end="url(#arr)"/>')
            if f["label"]:
                segs = list(zip(pts, pts[1:]))
                (x1, y1), (x2, y2) = max(segs, key=lambda sg: abs(sg[0][0] - sg[1][0]) + abs(sg[0][1] - sg[1][1])) \
                    if len(segs) > 1 and abs(segs[0][0][0] - segs[0][1][0]) + abs(segs[0][0][1] - segs[0][1][1]) < 40 else segs[0]
                lx, ly = (x1 + x2) / 2, (y1 + y2) / 2
                if abs(x1 - x2) < 1:
                    lx += 6; anchor = "start"
                else:
                    ly -= 6; anchor = "middle"
                s.append(f'<text x="{lx:.0f}" y="{ly:.0f}" font-size="10.5" fill="#2453C4" text-anchor="{anchor}">{escape(f["label"])}</text>')
        for n in self.nodes.values():
            x, y, w, h = self._box(n)
            cx, cy = x + w / 2, y + h / 2
            stroke = "#B42318" if n["issue"] else "#3a4654"
            if n["kind"] in ("start", "end"):
                sw = 1.5 if n["kind"] == "start" else 3.5
                s.append(f'<circle cx="{cx}" cy="{cy}" r="{w / 2}" fill="#ffffff" stroke="{stroke}" stroke-width="{sw}"/>')
                lines = textwrap.wrap(n["label"], 16)
                for i, line in enumerate(lines):
                    s.append(f'<text x="{cx}" y="{y + h + 14 + i * 12}" font-size="10.5" fill="#2b3440" text-anchor="middle">{escape(line)}</text>')
            elif n["kind"] == "xor":
                s.append(f'<polygon points="{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}" fill="#fff8e6" stroke="{stroke}" stroke-width="1.5"/>')
                s.append(f'<text x="{cx}" y="{cy + 5}" font-size="16" font-weight="700" fill="#3a4654" text-anchor="middle">×</text>')
                lines = textwrap.wrap(n["label"], 18)
                for i, line in enumerate(lines):
                    s.append(f'<text x="{cx}" y="{y - 6 - (len(lines) - 1 - i) * 12}" font-size="10.5" fill="#2b3440" text-anchor="middle">{escape(line)}</text>')
            else:
                fill = "#fdecea" if n["issue"] else "#ffffff"
                s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
                lines = textwrap.wrap(n["label"], 19)[:4]
                start = cy - (len(lines) - 1) * 6.5
                for i, line in enumerate(lines):
                    s.append(f'<text x="{cx}" y="{start + i * 13 + 4}" font-size="11" fill="#18212c" text-anchor="middle">{escape(line)}</text>')
                if n["issue"]:
                    s.append(f'<circle cx="{x + w - 4}" cy="{y + 4}" r="8" fill="#B42318"/>'
                             f'<text x="{x + w - 4}" y="{y + 8}" font-size="11" font-weight="700" fill="#fff" text-anchor="middle">!</text>')
        s.append('</g>')
        if any(n["issue"] for n in self.nodes.values()):
            s.append(f'<g transform="translate(1,{top + height + 14})"><rect width="14" height="14" rx="3" fill="#fdecea" stroke="#B42318"/>'
                     '<text x="20" y="11" font-size="11" fill="#5b6878">Pain point (see pain-point analysis)</text></g>')
        s.append('</svg>')
        return "\n".join(s)

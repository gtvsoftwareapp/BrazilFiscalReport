# Copyright (C) 2021-2022 Edson Bernardino <edsones at yahoo.com.br>
# Copyright (C) 2024 Engenere - Antônio S. Pereira Neto <neto@engenere.one>

import warnings
import xml.etree.ElementTree as ET
from io import BytesIO

from barcode.codex import Code128
from barcode.writer import SVGWriter

from ..utils import (
    chunks,
    format_cpf_cnpj,
    get_date_utc,
    get_tag_text,
)
from ..xfpdf import xFPDF


class DaCCe(xFPDF):
    """
    Document generation:
    DACCe - Documento Auxiliar da Carta de Correção Eletrônica
    Compatível com NFe e CTe
    """

    def __init__(self, xml=None, emitente=None, image=None):
        super().__init__("P", "mm", "A4")
        self.set_auto_page_break(auto=False, margin=10.0)
        self.set_title("DACCe")

        root = ET.fromstring(xml)

        # Detecta dinamicamente o namespace
        namespace_uri = root.tag.split("}")[0].strip("{")
        URL = f".//{{{namespace_uri}}}"

        # Identifica se é NFe ou CTe
        is_nfe = "nfe" in namespace_uri.lower()

        det_event = root.find(f"{URL}detEvento")
        inf_event = root.find(f"{URL}infEvento")
        ret_event = root.find(f"{URL}retEvento")
        inf_ret_event = ret_event.find(f"{URL}infEvento")

        self.add_page(orientation="P", format="A4")

        # Emitente
        self.rect(x=10, y=10, w=190, h=33, style="")
        self.line(90, 10, 90, 43)

        text = ""
        emitente_nome = ""
        if emitente:
            emitente_nome = emitente["nome"]
            text = (
                f"{emitente['end']}\n"
                f"{emitente['bairro']}\n"
                f"{emitente['cidade']} - {emitente['uf']} {emitente['fone']}"
            )

        if image:
            col_ = 23
            col_end = 28
            w_ = 67
            self.image(image, 12, 12, 12)
        else:
            col_ = 11
            col_end = 24
            w_ = 80

        self.set_xy(x=col_, y=16)
        self.set_font("Helvetica", "B", 10)
        self.multi_cell(w=w_, h=4, text=emitente_nome, border=0, align="C", fill=False)
        self.set_xy(x=11, y=col_end)
        self.set_font("Helvetica", "", 8)
        self.multi_cell(w=80, h=4, text=text, border=0, align="C", fill=False)

        # Cabeçalho CC-e
        doc_title = "CC-e de Nota Fiscal Eletrônica" if is_nfe else "CC-e de Conhecimento de Transporte Eletrônico"
        self.set_font("Helvetica", "B", 10)
        self.text(x=118, y=16, text="Representação Gráfica de CC-e")
        self.set_font("Helvetica", "I", 9)
        self.text(x=123, y=20, text=f"({doc_title})")

        self.set_font("Helvetica", "", 8)
        self.text(
            x=92, y=30, text="ID do Evento: {}".format(inf_event.attrib.get("Id")[2:])
        )

        dt, hr = get_date_utc(get_tag_text(node=inf_event, url=URL, tag="dhEvento"))
        self.text(x=92, y=35, text=f"Criado em: {dt} {hr}")

        dt, hr = get_date_utc(
            get_tag_text(node=inf_ret_event, url=URL, tag="dhRegEvento")
        )
        n_prot = get_tag_text(node=inf_ret_event, url=URL, tag="nProt")
        self.text(x=92, y=40, text=f"Protocolo: {n_prot} - Registrado na SEFAZ em: {dt} {hr}")

        # Mensagem de aviso
        self.rect(x=10, y=47, w=190, h=50, style="")
        self.line(10, 83, 200, 83)

        self.set_xy(x=11, y=48)
        text = (
            "De acordo com as determinações legais vigentes, vimos por "
            "meio desta comunicar-lhe que a Nota Fiscal, "
            "abaixo referenciada, contém irregularidades que estão "
            "destacadas e suas respectivas correções. Solicitamos que "
            "sejam aplicadas essas correções ao executar seus "
            "lançamentos fiscais."
        )
        self.set_font("Helvetica", "", 8)
        self.multi_cell(w=185, h=4, text=text, border=0, align="L", fill=False)

        # Chave da NFe ou CTe
        tag_chave = "chNFe" if is_nfe else "chCTe"
        key = get_tag_text(node=inf_event, url=URL, tag=tag_chave)

        # Código de barras
        svg_img_bytes = BytesIO()
        Code128(key, writer=SVGWriter()).write(
            svg_img_bytes, options={"write_text": False}
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            self.image(svg_img_bytes, x=127, y=60, w=73, h=8)

        self.set_font("Helvetica", "", 7)
        self.text(x=130, y=78, text=" ".join(chunks(key, 4)))

        self.set_font("Helvetica", "B", 9)

        # CNPJ do destinatário
        cnpj_dest = get_tag_text(node=inf_ret_event, url=URL, tag="CNPJDest")
        if not cnpj_dest:
            cnpj_dest = get_tag_text(node=inf_ret_event, url=URL, tag="CNPJ")

        text = f"CNPJ Destinatário:  {format_cpf_cnpj(cnpj_dest)}"
        self.text(x=12, y=71, text=text)

        # Nota + Série
        nf_num = f"{int(key[25:34]):011,}".replace(",", ".")
        nf_serie = key[22:25]
        self.text(x=12, y=76, text=f"Nota Fiscal: {nf_num} - Série: {nf_serie}")

        # Condições de uso
        self.set_xy(x=11, y=84)
        text = get_tag_text(node=det_event, url=URL, tag="xCondUso")
        self.set_font("Helvetica", "I", 7)
        self.multi_cell(w=185, h=3, text=text, border=0, align="L", fill=False)

        # Correções
        self.set_font("Helvetica", "B", 9)
        self.text(x=11, y=103, text="CORREÇÕES A SEREM CONSIDERADAS")

        self.rect(x=10, y=104, w=190, h=170, style="")

        self.set_xy(x=11, y=106)
        text = get_tag_text(node=det_event, url=URL, tag="xCorrecao")
        self.set_font("Helvetica", "", 8)
        self.multi_cell(w=185, h=4, text=text, border=0, align="L", fill=False)

        # Rodapé
        self.set_xy(x=11, y=265)
        text = (
            "Este documento é uma representação gráfica da CC-e e "
            "foi impresso apenas para sua informação e não possui validade "
            "fiscal.\nA CC-e deve ser recebida e mantida em arquivo "
            "eletrônico XML e pode ser consultada através dos portais "
            "das SEFAZ."
        )

        self.set_font("Helvetica", "I", 8)
        self.multi_cell(w=185, h=4, text=text, border=0, align="C", fill=False)

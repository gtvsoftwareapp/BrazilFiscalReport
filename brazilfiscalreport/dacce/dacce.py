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

        # Detecta namespace padrão do XML
        namespace_uri = root.tag.split("}")[0].strip("{")
        URL = f".//{{{namespace_uri}}}"

        # Função auxiliar para extrair texto com namespace, retornando string vazia se não encontrado
        def find_text_ns(node, tag):
            if node is None:
                return ""
            return node.findtext(f"{URL}{tag}", default="").strip()

        # Função para remover namespace do tag
        def strip_ns(tag):
            return tag.split('}', 1)[-1] if '}' in tag else tag

        is_nfe = "nfe" in namespace_uri.lower()

        det_event = root.find(f"{URL}detEvento")
        inf_event = root.find(f"{URL}infEvento")
        ret_event = root.find(f"{URL}retEvento")
        inf_ret_event = ret_event.find(f"{URL}infEvento") if ret_event is not None else None

        self.add_page(orientation="P", format="A4")

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

        doc_title = "CC-e de Nota Fiscal Eletrônica" if is_nfe else "CC-e de Conhecimento de Transporte Eletrônico"
        self.set_font("Helvetica", "B", 10)
        self.text(x=118, y=16, text="Representação Gráfica de CC-e")
        self.set_font("Helvetica", "I", 9)
        self.text(x=123, y=20, text=f"({doc_title})")

        self.set_font("Helvetica", "", 8)
        if inf_event is not None:
            try:
                evento_id = inf_event.attrib.get("Id")
                self.text(x=92, y=30, text=f"ID do Evento: {evento_id[2:]}")
            except Exception as e:
                print("[ERRO] Falha ao extrair ID do Evento:", e)

        try:
            dh_evento_str = find_text_ns(inf_event, "dhEvento")
            dt, hr = get_date_utc(dh_evento_str)
            self.text(x=92, y=35, text=f"Criado em: {dt} {hr}")
        except Exception as e:
            print("[ERRO] Falha ao extrair dhEvento:", e)

        try:
            if inf_ret_event is not None:
                dh_reg_str = find_text_ns(inf_ret_event, "dhRegEvento")
                n_prot = find_text_ns(inf_ret_event, "nProt")

                if dh_reg_str and n_prot:
                    dt, hr = get_date_utc(dh_reg_str)
                    self.text(x=92, y=40, text=f"Protocolo: {n_prot} - Registrado na SEFAZ em: {dt} {hr}")
                else:
                    print("[AVISO] Protocolo ou data de registro não encontrados no inf_ret_event.")
            else:
                print("[AVISO] inf_ret_event está ausente no XML.")
        except Exception as e:
            print("[ERRO] Falha ao extrair dados do protocolo:", e)



        self.rect(x=10, y=47, w=190, h=50, style="")
        self.line(10, 83, 200, 83)

        self.set_xy(x=11, y=48)
        aviso = (
            "De acordo com as determinações legais vigentes, vimos por "
            "meio desta comunicar-lhe que a Nota Fiscal, "
            "abaixo referenciada, contém irregularidades que estão "
            "destacadas e suas respectivas correções. Solicitamos que "
            "sejam aplicadas essas correções ao executar seus "
            "lançamentos fiscais."
        )
        self.set_font("Helvetica", "", 8)
        self.multi_cell(w=185, h=4, text=aviso, border=0, align="L", fill=False)

        tag_chave = "chNFe" if is_nfe else "chCTe"
        try:
            key = find_text_ns(inf_event, tag_chave)
        except Exception as e:
            print("[ERRO] Falha ao extrair chave:", e)
            key = ""

        try:
            svg_img_bytes = BytesIO()
            Code128(key, writer=SVGWriter()).write(
                svg_img_bytes, options={"write_text": False}
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                self.image(svg_img_bytes, x=127, y=60, w=73, h=8)
        except Exception as e:
            print("[ERRO] Falha ao gerar código de barras:", e)

        self.set_font("Helvetica", "", 7)
        self.text(x=130, y=78, text=" ".join(chunks(key, 4)))

        self.set_font("Helvetica", "B", 9)
        
        try:
            if is_nfe:
                cnpj_dest = find_text_ns(inf_ret_event, "CNPJDest")
                if not cnpj_dest:
                    cnpj_dest = find_text_ns(inf_ret_event, "CNPJ")
                label = "CNPJ Destinatário"
            else:
                cnpj_dest = find_text_ns(inf_event, "CNPJ") or find_text_ns(inf_event, "CPF")
                label = "Autor do Evento"

            self.text(x=12, y=71, text=f"{label}:  {format_cpf_cnpj(cnpj_dest)}")
        except Exception as e:
            print("[ERRO] Falha ao extrair CNPJ/Autor do Evento:", e)


        try:
            nf_num = f"{int(key[25:34]):011,}".replace(",", ".")
            nf_serie = key[22:25]
            self.text(x=12, y=76, text=f"Nota Fiscal: {nf_num} - Série: {nf_serie}")
        except Exception as e:
            print("[ERRO] Falha ao extrair número ou série da nota:", e)

        self.set_xy(x=11, y=84)
        
        try:
            text = find_text_ns(det_event, "xCondUso")
        except Exception as e:
            print("[ERRO] Falha ao extrair xCondUso:", e)
            text = ""
        self.set_font("Helvetica", "I", 7)
        self.multi_cell(w=185, h=3, text=text, border=0, align="L", fill=False)

        self.set_font("Helvetica", "B", 9)
        self.text(x=11, y=103, text="CORREÇÕES A SEREM CONSIDERADAS")

        self.rect(x=10, y=104, w=190, h=170, style="")

        self.set_xy(x=11, y=106)

        # Extrair o texto de correção (xCorrecao para NFe ou infCorrecao para CTe)
        text = ""
        try:
            # tenta extrair diretamente xCorrecao (NFe)
            text = find_text_ns(det_event, "xCorrecao")
        except Exception:
            text = ""

        if not text:
            try:
                correcao_lista = []

                # Busca o elemento evCCeCTe ignorando namespace
                ev_cce_cte = None
                for child in det_event:
                    if strip_ns(child.tag) == "evCCeCTe":
                        ev_cce_cte = child
                        break

                if ev_cce_cte is not None:
                    for inf_corr in ev_cce_cte:
                        if strip_ns(inf_corr.tag) == "infCorrecao":
                            grupo = ""
                            campo = ""
                            valor = ""
                            nro_item = ""

                            for tag_child in inf_corr:
                                tag_name = strip_ns(tag_child.tag)
                                if tag_name == "grupoAlterado":
                                    grupo = tag_child.text or ""
                                elif tag_name == "campoAlterado":
                                    campo = tag_child.text or ""
                                elif tag_name == "valorAlterado":
                                    valor = tag_child.text or ""
                                elif tag_name == "nroItemAlterado":
                                    nro_item = tag_child.text or ""

                            linha = f"Campo: {campo} | Valor: {valor}"
                            if grupo:
                                linha += f" | Grupo: {grupo}"
                            if nro_item:
                                linha += f" | Item: {nro_item}"

                            correcao_lista.append(linha)

                text = "\n".join(correcao_lista)
            except Exception as e:
                print("[ERRO] Falha ao extrair informações de correção:", e)
                text = ""

        self.set_font("Helvetica", "", 8)
        self.multi_cell(w=185, h=4, text=text, border=0, align="L", fill=False)

        self.set_xy(x=11, y=265)
        rodape = (
            "Este documento é uma representação gráfica da CC-e e "
            "foi impresso apenas para sua informação e não possui validade "
            "fiscal.\nA CC-e deve ser recebida e mantida em arquivo "
            "eletrônico XML e pode ser consultada através dos portais "
            "das SEFAZ."
        )
        self.set_font("Helvetica", "I", 8)
        self.multi_cell(w=185, h=4, text=rodape, border=0, align="C", fill=False)

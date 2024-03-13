import streamlit as st
import xml.etree.ElementTree as ET
import requests
import json
import decimal
import os


def extract_fields_from_xml(xml_content):
    root = ET.fromstring(xml_content)
    fields_dict = {}
    related_documents = []
    for elem in root.iter():
        tag = elem.tag.split('}')[-1]
        attributes = {
            f'attr_{attr.split("}")[-1]}': value
            for attr, value in elem.attrib.items()
        }
        if tag == 'DoctoRelacionado':
            uuid = ""
            amount = 0
            last_balance = 0
            currency = ""
            exchange = 0
            installment = 1
            for attr, value in elem.attrib.items():
                if attr == 'IdDocumento':
                    uuid = value
                if attr == 'ImpPagado':
                    amount = value
                if attr == 'ImpSaldoAnt':
                    last_balance = value
                if attr == 'MonedaDR':
                    currency = value
                if attr == 'EquivalenciaDR':
                    exchange = value
                if attr == 'NumParcialidad':
                    installment = value
            related_documents.append({
                "uuid": uuid,
                "amount": amount,
                "last_balance": last_balance,
                "currency": currency,
                "exchange": exchange,
                "installment": installment,
                "taxability": "01",
                "taxes": []
            })
                
        fields = {tag: elem.text} if elem.text else {}
        fields.update(attributes)
        fields_dict.update(fields)
    return fields_dict, related_documents


def generate_txt(json_data):
    try:
        txt_lines = []

        # Header - TipoRegistroCONIF=Encabezado
        txt_lines.append(
            "TipoRegistroCONIF=Encabezado|FolioReferencia={}-{}|DomicilioFiscalReceptor={}|VersionCFDI=4.0|cfdiExportacion=01|cfdiRegimenFiscalReceptor={}|TipoDocumento=RecepcionDePagos|LugarExpedicion=66230|Moneda=XXX|SubTotal=0|Total=0|cfdiTipoRelacion=|RegimenFiscalEmisor={}|NoDeOrden=ComplementoPago|NumProveedor=10117289|EmailTracking=|Observaciones=|RI=0101163|"
            .format(json_data["series"], json_data["folio_number"],
                    json_data["customer"]["address"]["zip"],
                    json_data["customer"]["tax_system"]))

        # Receptor - TipoRegistroCONIF=Receptor
        txt_lines.append(
            f"TipoRegistroCONIF=Receptor|DomicilioFiscalReceptor={json_data['customer']['address']['zip']}|RFC={json_data['customer']['tax_id']}|IdExterno=1265|nombre={json_data['customer']['legal_name']}|cfdiUsoCFDI=CP01|NumRegIdTrib=|ResidencialFiscal={json_data['customer']['address']['country']}|\n"
        )
        print(2)
        # Pagos - TipoRegistroCONIF=Pagos
        txt_lines.append(
            "TipoRegistroCONIF=Pagos|CodigoMultiple=pagos20|TotalTrasladosBaseIVA16=14023.61|TotalTrasladosImpuestoIVA16=2243.78|MontoTotalPagos=16267.39|\n"
        )
        print(3)
        # Pago20Pago - TipoRegistroCONIF=pago20Pago
        payment = json_data['complements'][0]['data'][0]['related_documents'][
            0]
        txt_lines.append(
            f"TipoRegistroCONIF=pago20Pago|pagoTipoCambioP=1.0000|CodigoMultiple=pago20|pagoFechaPago={payment['date']}|pagoFormaDePagoP={payment['payment_form']}|pagoMonedaP={payment['currency']}|pagoMonto={payment['amount']}|pagoNumOperacion={payment['numOperacion']}|\n"
        )

        # Pago20DoctoRel - TipoRegistroCONIF=pago20DoctoRel
        related_doc = payment["related_documents"][0]
        txt_lines.append(
            f"TipoRegistroCONIF=pago20DoctoRel|EquivalenciaDR=1|CodigoMultiple=pago20|ObjetoImpDR=02|pagoIdDocumento={related_doc['uuid']}|pagoSerie=|pagoFolio=105130|pagoMonedaDR={related_doc['currency']}|pagoMetodoDePagoDR=PPD|pagoNumParcialidad=1|pagoImpSaldoAnt={related_doc['last_balance']}|pagoImpPagado={related_doc['amount']}|pagoImpSaldoInsoluto={float(related_doc['last_balance']) - float(related_doc['amount'])}|\n"
        )

        # TrasladoDR - TipoRegistroCONIF=TrasladoDR
        tax = related_doc["taxes"][0]
        txt_lines.append(
            f"TipoRegistroCONIF=TrasladoDR|CodigoMultiple=pago20DoctoRel|BaseDR={tax['base']}|ImpuestoDR={tax['type']}|TipoFactorDR=Tasa|TasaOCuotaDR={tax['rate']}|ImporteDR={float(tax['base']) * float(tax['rate'])}|\n"
        )

        # TrasladoP - TipoRegistroCONIF=TrasladoP
        txt_lines.append(
            f"TipoRegistroCONIF=TrasladoP|CodigoMultiple=pago20|TasaOCuotaP={tax['rate']}|TipoFactorP=Tasa|ImpuestoP={tax['type']}|BaseP={tax['base']}|ImporteP={float(tax['base']) * float(tax['rate'])}|\n"
        )

        # Cuerpo - TipoRegistroCONIF=Cuerpo
        txt_lines.append(
            "TipoRegistroCONIF=Cuerpo|cfdiObjetoImp=01|Renglon=1|Cantidad=1|Concepto=Pago|PUnitario=0|Importe=0|cfdiClaveProdServ=84111506|cfdiClaveUnidad=ACT|\n"
        )

        # FinDocumento - TipoRegistroCONIF=FinDocumento
        txt_lines.append("TipoRegistroCONIF=FinDocumento|")

        return "\n".join(txt_lines)
    except (KeyError, TypeError) as e:
        raise Exception(f"Error generating TXT: {e}")


def main():
    # mas de un archivo
    # descarga del zip creado de facturapi
    st.title("XML Content Extractor")
    order_number = st.text_input(label="Order Number")
    uploaded_files = st.file_uploader("Upload XML file",
                                      type=".xml",
                                      accept_multiple_files=True)

    if uploaded_files is not None:
        # Read the file contents
        # xml_content = uploaded_file.read()
        for f in uploaded_files:
            xml_content = f.read()

            # Extract the fields from the XML content
            fields_dict, related_documents = extract_fields_from_xml(xml_content)
            # Update the 'data' dictionary with the extracted values
            data = {
                "type": "P",
                "complements": [{
                    "type": "pago",
                    "data": [{
                        "payment_form": fields_dict.get('attr_FormaDePagoP'),
                        "currency": fields_dict.get('attr_MonedaP'),
                        "exchange": fields_dict.get('attr_TipoCambioP'),
                        "date": fields_dict.get('attr_FechaPago'),
                        "numOperacion": fields_dict.get('attr_NumOperacion'),
                        "nomBancoOrdExt": fields_dict.get('attr_NomBancoOrdExt'),
                        "related_documents": related_documents
                    }]
                }],
                "customer": {
                    "legal_name": fields_dict.get('attr_Nombre'),
                    #"email": "mail del cliente",
                    "tax_id": fields_dict.get('attr_Rfc'),
                    "tax_system": fields_dict.get('attr_RegimenFiscal'),
                    "address": {
                        "street": "calle dirección de cliente",
                        "exterior": "numero exterior de dirección del cliente",
                        "interior": "Numero interior de direccion de cliente",
                        "neighborhood": "Colonia del cliente",
                        "municipality": "municipio de dirección del cliente",
                        "zip": fields_dict.get('attr_DomicilioFiscalReceptor'),
                        "state": "Calle de dirección del cliente",
                        "country": "MEX"
                    }
                },
                "series": "P",
                "folio_number": fields_dict.get('attr_Folio'),
                "pdf_custom_section": f"<p>Pedido #{order_number}</p>",
            }

            data = json.dumps(data)
            headers = {
                "Content-Type": "application/json",
            }
            url = "https://www.facturapi.io/v2/invoices/"
            secret_key = "sk_live_0J3nDa18dROAj9vX7EBP4x1D"
            secret_key = "sk_live_kxjaOmXonEpV7K6gv270EbKmzKJ9BZAQd4Lrl0bR2P"
            response = requests.post(url,
                                     headers=headers,
                                     data=data,
                                     auth=(secret_key, secret_key))
            st.write(response.content)
            if response.status_code != 200:
                print("Error - ", response.content)
                st.write("Hubo un error:")
                st.write(response.json().get('message', None))
            else:
                data = response.json()
                invoice_id = data["id"]
                download_url = f"https://www.facturapi.io/v2/invoices/{invoice_id}/zip"
                response = requests.get(url=download_url,
                                        auth=(secret_key, secret_key))
                st.write(f)
                st.download_button(
                    label="Descargar ZIP",
                    data=response.content,
                    file_name='pago_zip.zip',
                )
            return {"data": data}


if __name__ == "__main__":
    main()

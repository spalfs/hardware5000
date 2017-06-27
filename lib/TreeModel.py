from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex
from PyQt5.QtGui import QBrush, QColor
from ast import literal_eval
import xml.etree.ElementTree as ET

from lib.xmllib import find
from lib.TreeItem import TreeItem

class TreeModel(QAbstractItemModel):
    def __init__(self, path, parent=None):
        super(TreeModel, self).__init__(parent)

        self.rootItem = TreeItem(("Hardware", "Hardware Comment", "Connected Parameter", "Parameter Comment"))

        self.setupModel(path)

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.BackgroundRole:
            if item.depth == 0:
                return QBrush(QColor(157,159,85))
            elif item.depth == 1:
                return QBrush(QColor(85,157,159))
            elif item.depth == 2:
                return QBrush(QColor(85,120,159))
            elif item.depth == 3:
                return QBrush(QColor(159,85,120))
            elif item.depth == 4:
                return QBrush(QColor(120,159,85))

        if role == Qt.EditRole:
            return item.data(index.column())

        if role != Qt.DisplayRole:
            return None

        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def setData(self, index, value, role):
        try:
            XMLRoot = self.XMLTree.getroot()
            item = index.internalPointer()

            element = find(XMLRoot, item.data(0), item.data(1), item.data(2))

            if index.column() == 0:
                element.tag = value
            elif index.column() == 1:
                element.text = value
            elif index.column() == 2:
                for key in list(element.attrib):
                    del element.attrib[key]
                dValue = literal_eval(value)
                for key in dValue:
                    element.set(key,dValue[key])

            item.setData(value,index.column())
            return True

        except:
            return False

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.rootItem.data(section)

        return None

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def setupModel(self, path):
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()

        self.base = TreeItem((path.split('/')[-1],"","",""), self.rootItem)
        self.rootItem.appendChild(self.base)

        modules = self.getModules()
        self.draw(modules)

    def getModules(self):
        modules = []

        for module in self.root.iter("Module"):

            inputs = []
            outputs = []

            address = module.findall("./Ports/")[0].attrib["Address"]
            hardware = module.attrib['ParentModule']
            hcomment = module.attrib['Name']

            if hcomment.find("Cube") != -1 or hcomment.find("K070") != -1:
                hardware = hcomment
                hcomment = ""
            else:
                hardware = hardware + ":" + address

            for search in ["InputTag", "InAliasTag", "OutputTag", "OutAliasTag"]:
                for tags in module.iter(search):
                    for comment in tags.iter("Comment"):
                        if search[0] == "I":
                            inputs.append({ "hardware" : hardware + ":" + search[0] + comment.attrib['Operand'],
                                            "hcomment" : comment.text})
                        else:
                            outputs.append({ "hardware" : hardware + ":" + search[0] + comment.attrib['Operand'],
                                             "hcomment" : comment.text})

            inputs = [self.getParameterConnection(i) for i in inputs]
            inputs = [self.getParameterComment(i) for i in inputs]

            outputs = [self.getParameterConnection(o) for o in outputs]
            outputs = [self.getParameterComment(o) for o in outputs]

            modules.append({'hardware'  : hardware,
                            'hcomment'  : hcomment,
                            'inputs'    : inputs,
                            'outputs'   : outputs})

        return modules

    def treeHardware(self, parent, puts):
        for put in puts:
            if len(put['hardware'].split(".")) == 2:
                childItem = TreeItem((put['hardware'], put['hcomment'], put['parameter'], put['pcomment']), parent, 3)
                parent.appendChild(childItem)

        for put in puts:
            pModule = put['hardware'].split(".")
            if len(pModule) == 3:
                pModule = ".".join(pModule[0:2])

                root = self.base
                hwCount = root.childCount()
                for i in range(hwCount):

                    hardware = root.child(i)
                    childCount = hardware.childCount()
                    for j in range(childCount):

                        p = hardware.child(j)
                        moduleCount = p.childCount()
                        for k in range(moduleCount):

                            module = p.child(k)
                            if module.data(0) ==  pModule:
                                childItem = TreeItem((put['hardware'], put['hcomment'], put['parameter'], put['pcomment']), module, 4)
                                module.appendChild(childItem)

    def draw(self, modules):
        for module in modules:
            if len(module['inputs']) or len(module['outputs']):
                item = TreeItem((module['hardware'], module['hcomment'],"",""), self.base, 1)
                self.base.appendChild(item)

                inputs = TreeItem(("Inputs","","",""), item, 2)
                item.appendChild(inputs)
                self.treeHardware(inputs, module['inputs'])

                outputs = TreeItem(("Outputs","","",""), item, 2)
                item.appendChild(outputs)
                self.treeHardware(outputs, module['outputs'])

        #for i in range(4):
        #    self.TreeWidget.resizeColumnToContents(i)

    def getParameterComment(self, comment):
        s = comment['parameter'].split('.')
        if len(s) != 1:
            programName = comment['parameter'].split('.')[0][1:]
            tagName = comment['parameter'].split('.')[1]

            for program in self.root.iter("Program"):
                if program.attrib['Name'] == programName:
                    for tag in program.iter("Tag"):
                        if tag.attrib['Name'] == tagName:
                            for e in tag:
                                potential = tag.findall("Description")
                                if len(potential):
                                    comment['pcomment'] = potential[0].text
                                    return comment

        comment['pcomment'] = ''
        return comment

    def getParameterConnection(self, comment):
        for parameter in self.root.iter("ParameterConnection"):
            e1 = parameter.attrib['EndPoint1']
            e2 = parameter.attrib['EndPoint2']

            if e1[0] == "\\":
                hw = e2
                tag= e1
            else:
                hw = e1
                tag= e2

            hw = hw.split(":")
            hw[1] = hw[1].upper()
            hw = ":".join(hw)

            if comment['hardware'] == hw:
                comment['parameter'] = tag
                return comment

        comment['parameter'] = ""
        return comment

    def setColor(self, color, node=None):
        if node is None:
            node = self.rootItem
        for i in range(node.childCount()):
            node.child(i).setColorState(color)
            self.setColor(color, node.child(i))

    def save(self,path=None):
        if path is None:
            path = self.path

        self.resetChanged()
        try:
            self.XMLTree.write(path)
        except:
            print("save error")

    def find(self, root, tag, text, attrib):
        for element in root.iter(tag):
            tryText = str(element.text)
            if tryText == "None":
                tryText = ""
            if tryText == text and str(element.attrib) == atrrib:
                return element

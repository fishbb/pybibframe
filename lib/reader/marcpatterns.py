'''
Declarations used to elucidate MARC model
'''
#Just set up some flags
#BOUND_TO_WORK = object()
#BOUND_TO_INSTANCE = object()

#Full MARC field list: http://www.loc.gov/marc/bibliographic/ecbdlist.html

#This line must be included
from bibframe.reader.util import *

MATERIALIZE = {
'100': ('creator', {'marcrType': 'Person'}),
'110': ('creator', {'marcrType': 'Organization'}),
'111': ('creator', {'marcrType': 'Meeting'}),

'130': ('uniformMemberOf', {'marcrType': 'Collection'}),
'240a': ('uniformMemberOf', {'marcrType': 'Collection'}),
'243a': ('uniformMemberOf', {'marcrType': 'Collection'}),
'730': ('uniformMemberOf', {'marcrType': 'Collection'}),
'830': ('uniformMemberOf', {'marcrType': 'Collection'}),

'260': ('publication', {'marcrType': 'ProviderEvent'}),
'264': ('publication', {'marcrType': 'ProviderEvent'}),

'264-x3': ('manufacture', {'marcrType': 'ProviderEvent'}),
'264-x2': ('distribution', {'marcrType': 'ProviderEvent'}),
'264-x1': ('publication', {'marcrType': 'ProviderEvent'}),
'264-x0': ('production', {'marcrType': 'ProviderEvent'}),

'260a': ('providerAgent', {'marcrType': 'Place'}),
'260b': ('providerAgent', {'marcrType': 'Agent'}),
'260e': ('providerAgent', {'marcrType': 'Place'}),
'260f': ('providerAgent', {'marcrType': 'Agent'}),
'264a': ('providerAgent', {'marcrType': 'Place'}),
'264b': ('providerAgent', {'marcrType': 'Agent'}),

#'300': ('physicalDescription', {'marcrType': 'Measurement'}),

'600': ('subject', {'marcrType': 'Person'}),
'610': ('subject', {'marcrType': 'Organization'}),
'611': ('subject', {'marcrType': 'Meeting'}),

'630': ('uniformTitle', {'marcrType': 'Title'}),
'650': ('subject', {'marcrType': 'Topic'}),
'651': ('subject', {'marcrType': 'Geographic'}),
'655': ('genre', {'marcrType': 'Genre'}),

'700': ('contributor', {'marcrType': 'Person'}),
'710': ('contributor', {'marcrType': 'Organization'}),
'711': ('contributor', {'marcrType': 'Meeting'}),

'740': ('contributor', {'marcrType': 'Person'}),
}

MATERIALIZE_VIA_ANNOTATION = {
'852': ('institution', 'HeldItem', {'holderType': 'Library'},),
}

#A refinement is a relationship from one mapping to another in order to refine
#
#REFINEMENTS = {
#'700a': ('700e', normalizeparse, action.replace)
#}


FIELD_RENAMINGS = {
# where do we put LDR info, e.g. LDR 07 / 19 positions = mode of issuance
'010a': 'lccn',
#Don't do a simple field renaming of ISBN because
'017a': 'legalDeposit',
'019a': 'bfp:localControlNumber',
#'020a': 'isbn',
'022a': 'issn',
'024a': 'bfp:otherControlNumber',
'025a': 'lcOverseasAcq',
'034a': 'cartographicMathematicalDataScaleStatement', #Rebecca & Sally suggested this should effectively be a merge with 034a
'034b': 'cartographicMathematicalDataProjectionStatement',
'034c': 'cartographicMathematicalDataCoordinateStatement',
'035a': 'systemControlNumber',
'037a': 'stockNumber',
'040a': 'catalogingSource',
'050a': 'lcCallNumber',
'050b': 'lcItemNumber',
'0503': 'material',
'060a': 'bfp:nlmCallNumber',
'060b': 'bfp:nlmItemNumber',
'061a': 'bfp:nlmCopyStatement',
'070a': 'bfp:nalCallNumber.',
'070b': 'bfp:nalItemNumber', 
'071a': 'bfp:nalCopyStatement',
'082a': 'deweyNumber',
'100a': 'label',
'100b': 'numeration',
'100c': 'titles',
'100d': 'date',  #Note: there has been discussion about removing this, but we are not sure we get reliable ID.LOC lookups without it.  If it is removed, update augment.py 
'110a': 'label',
'110d': 'date',
'111a': 'label',
'111d': 'date',
'130a': 'label',
'130a': 'title',
'130n': 'workSection', 
'240a': 'title',
'730a': 'label',
'830a': 'title',
'130l': 'language',
'041a': 'language',
'210a': 'abbreviatedTitle',
'222a': 'keyTitle',
'240d': 'legalDate',
'240h': 'medium',
'240m': 'musicMedium',  	
'240r': 'musicKey',
'245a': 'title',
'245b': 'subtitle',
'245c': 'statement',
'245f': 'inclusiveDates',
'245h': 'medium',
'245k': 'formDesignation',
'246a': 'titleVariation',
'246f': 'titleVariationDate',
'247a': 'formerTitle',
'250a': 'edition',
'250b': 'edition',
'254a': 'musicalPresentation',
'255a': 'cartographicMathematicalDataScaleStatement',
'255b': 'cartographicMathematicalDataProjectionStatement',
'255c': 'cartographicMathematicalDataCoordinateStatement',
'256a': 'computerFilecharacteristics',
'260c': 'providerDate',
'260g': 'providerDate',
'264c': 'providerDate', 
'260a': 'providerPlace',
'260b': 'providerAgent',
'300a': 'extent',
'300b': 'otherPhysicalDetails',
'300c': 'dimensions',
'300e': 'accompanyingMaterial',
'300f': 'typeOfunit',
'300g': 'size',
'3003': 'materials',
'310a': 'publicationFrequency',
'310b': 'publicationDateFrequency',
'336a': 'contentCategory',
'336b': 'contentTypeCode',
'3362': 'bfp:contentTypeRDAsource',
'337a': 'mediaCategory',
'337b': 'mediaTypeCode',
'3372': 'bfp:medaiRDAsource',
'338a': 'carrierCategory',
'338b': 'bpf:carrierCategoryCode',
'3382': 'bpf:carrierRDASource',
'340a': 'physicalSubstance',
'340b': 'dimensions',
'340c': 'materialsApplied',
'340d': 'recordingTechnique',
'340e': 'physicalSupport',
'351a': 'orgazationMethod',
'351b': 'arrangement',
'351c': 'hierarchy',
'3513': 'materialsSpec',
'490a': 'seriesStatement',
'490v': 'seriesVolume',
'500a': 'note',
'501a': 'note',
'502a': 'dissertationNote',
'502b': 'degree',
'502c': 'grantingInstitution',
'502d': 'dissertationYear',
'502g': 'dissertationNote', 
'502o': 'dissertationID',
'504a': 'bibliographyNote',
'505a': 'contentsNote',
'506a': 'governingAccessNote',
'506b': 'jurisdictionNote',
'506c': 'physicalAccess',
'506d': 'authorizedUsers',
'506e': 'authorization',
'506u': 'uriNote',
'507a': 'representativeFractionOfScale',
'507b': 'remainderOfScale',
'508a': 'creditsNote',
'510a': 'citationSource', 
'510b': 'citationCoverage',
'510c': 'citationLocationWithinSource',
'510u': 'citationUri',
'511a': 'performerNote',
'513a': 'typeOfReport',
'513b': 'periodCoveredn',
'514a': 'dataQuality',
'515a': 'numberingPerculiarities', 
'516a': 'typeOfComputerFile',
'518a': 'dateTimePlace',
'518d': 'dateOfEvent',
'518o': 'otherEventInformation', 
'518p': 'placeOfEvent',
'520a': 'summary',
'520b': 'summaryExpansion',
'520c': 'assigningSource',
'520u': 'summaryURI',
'521a': 'intendedAudience',
'521b': 'intendedAudienceSource', 
'522a': 'geograhpicCoverage',
'525a': 'supplement',
'538a': 'systemDetails',
'526a': 'studyProgramName',
'526b': 'interestLevel',
'526c': 'readingLevel',
'530a': 'additionalPhysicalForm',
'533a': 'reproductionNote',
'534a': 'originalVersionNote',
'535a': 'locationOfOriginalsDuplicates',
'536a': 'fundingInformation',
'538a': 'systemDetails',
'540a': 'termsGoverningUse',
'541a': 'immediateSourceOfAcquisition',
'542a': 'informationRelatingToCopyrightStatus',
'544a': 'locationOfOtherArchivalMaterial',
'545a': 'biographicalOrHistoricalData',
'546a': 'languageNote',
'547a': 'formerTitleComplexity',
'550a': 'issuingBody',
'552a': 'entityAndAttributeInformation',
'555a': 'cumulativeIndexFindingAids',
'556a': 'informationAboutDocumentation',
'561a': 'ownership', 
'583a': 'action',
'600a': 'label',
'600d': 'date',
'610a': 'label',
'610d': 'date',  #Note: there has been discussion about removing this, but we are not sure we get reliable ID.LOC lookups without it.  If it is removed, update augment.py 
'650a': 'label',
'650d': 'date',
'651a': 'label',
'651d': 'date',
'630a': 'uniformTitle',
'630l': 'language',
'630a': 'label',
'630h': 'medium',
'630v': 'formSubdivision',
'630x': 'generalSubdivision',
'630y': 'chronologicalSubdivision',
'630z': 'geographicSubdivision',
'650a': 'label',
'650c': 'locationOfEvent',
'650v': 'formSubdivision',
'650x': 'generalSubdivision',
'650y': 'chronologicalSubdivision',
'650z': 'geographicSubdivision',
'651v': 'formSubdivision',
'651x': 'generalSubdivision',
'651y': 'chronologicalSubdivision',
'651z': 'geographicSubdivision',
'655a': 'label',
'6552': 'source', #Note: use this to trigger link authority lookup
'700a': 'label',
'700b': 'numeration',
'700c': 'titles',
'700d': 'date',  #Note: there has been discussion about removing this, but we are not sure we get reliable ID.LOC lookups without it.  If it is removed, update augment.py 
'710a': 'label',
'710d': 'date',
'711a': 'label',
'711d': 'date',
'880a': 'title',
'852a': 'location',
'852b': 'subLocation',
'852h': 'callNumber', 
'852n': 'code',
'852u': 'link',
'852e': 'streetAddress',
'856u': 'link',
}


WORK_FIELDS = set([
'010',
'028',
'035',
'040',
'041',
'050a', #Note: should be able to link directly to authority @ id.loc.gov authority/classification/####
'082',
'100',
'110',
'111',
'130',
'210',
'222',
'240',
'243',
'245',
'246',
'264',
'247',
'310',
'310',
'321',
'321',
'362',
'490',
'500',
'502',
'504',
'510',
'511',
'513',
'514',
'518',
'520',
'521',
'522',
'583',
'600',
'610',
'611',
'630',
'650',
'651',
'700',
'710',
'711',
'730',
'740',
'880',
])


INSTANCE_FIELDS = set([
'020',
'022',
'055',
'060',
'070',
'086',
'210',
'222',
'250',
'254',
'255',
'256',
'257',
'260',
'263',
'300',
'310',
'340',
'351',
'306',
'340',
'336',
'337',
'338',
'351',
'505',
'506',
'507',
'508',
'515',
'516',
'525',
'530',
'538',
'561',
'850',
'852',
'856',
])

ANNOTATIONS_FIELDS = set([
'852a',
'852b',
'852h',
'852n',
'852u',
'852e',
])

PROVIDER_EVENT_FIELDS = set([
'260a',
'260b',
'260c',
'260e',
'260f',
'260g',
'264a',
'264b',
'264c',
])

HOLDINGS_FIELDS = set([
'852',
])
